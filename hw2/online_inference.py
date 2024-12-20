from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, udf, length, when
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    IntegerType,
    BooleanType,
    ArrayType,
)
from pyspark.ml import PipelineModel
import pickle
from bloom_filter import BloomFilter
import os


# initialize spark
spark = (
    SparkSession.builder.appName("WikipediaBotFilterStreaming")
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

# define schema
schema = ArrayType(
    StructType(
        [
            StructField("id", LongType(), True),
            StructField("title", StringType(), True),
            StructField("user", StringType(), True),
            StructField("bot", BooleanType(), True),
            StructField("length", IntegerType(), True),
            StructField("wiki", StringType(), True),
            StructField("timestamp", StringType(), True),
            StructField("minor", BooleanType(), True),
            StructField("comment", StringType(), True),
        ]
    )
)


# load pre-trained model
model = PipelineModel.load("model/")

# load bloom filter
bloom_filter_path = "bloom_filter.pickle"


if os.path.exists(bloom_filter_path):
    with open(bloom_filter_path, "rb") as f:
        state = pickle.load(f)
    bloom_filter = BloomFilter.from_state(state)
    print(f"Loaded existing Bloom filter with {bloom_filter.size} entries.")
else:
    # init new bloom filter with expected items and false positive rate
    expected_items = 1000000
    false_positive_rate = 0.001
    bloom_filter = BloomFilter(expected_items, false_positive_rate)
    print("Initialized a new Bloom filter.")


# define processing
def process_batch(batch_df, epoch_id):
    global bloom_filter

    # serialize filter state and broadcast it
    bf_state = bloom_filter.get_state()
    bf_state_broadcast = spark.sparkContext.broadcast(bf_state)

    # define UDF to check if a record is already flagged as a bot
    def create_is_seen_udf():
        def is_seen(item_id):
            bf_state = bf_state_broadcast.value
            bf_local = BloomFilter.from_state(bf_state)
            return bf_local.contains(str(item_id))

        return udf(is_seen, BooleanType())

    is_seen_udf = udf(create_is_seen_udf(), BooleanType())

    # filter out records using bloom filter
    unseen_df = batch_df.withColumn("is_seen", is_seen_udf(col("id"))).filter(
        col("is_seen") == False
    )

    # check if filtered dataset is empty
    if unseen_df.rdd.isEmpty():
        print(f"Epoch {epoch_id}: No unseen traffic to process in this batch.")
        return

    # pre-process data
    unseen_df = unseen_df.withColumn(
        "comment_length",
        when(col("comment").isNull(), 0).otherwise(length(col("comment"))),
    )
    unseen_df = unseen_df.fillna(
        {"length": 0, "comment_length": 0, "minor": False, "bot": False, "comment": ""}
    )

    # apply the ML model to make additional processing
    predictions = model.transform(unseen_df)

    # identify potential bots based on model prediction
    bots_df = predictions.filter(col("prediction") >= 0.5)

    # add bot user to the bloom filter
    new_bot_identifiers = [row.user for row in bots_df.select("user").collect()]
    for bot_identifier in new_bot_identifiers:
        bloom_filter.add(bot_identifier)

    bloom_filter.resize(len(new_bot_identifiers))

    with open(bloom_filter_path, "wb") as f:
        pickle.dump(bloom_filter.get_state(), f)

    print(
        f"Epoch {epoch_id}: Processed {unseen_df.count()} unseen records, identified {len(new_bot_identifiers)} new bots."
    )


# read streaming data
raw_df = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", os.getenv("KAFKA_SERVER", "localhost:9092"))
    .option("subscribe", "wikipedia-edits")
    .option("failOnDataLoss", "false")
    .option("startingOffsets", "earliest")
    .load()
)


# prepare stream data into individual records
json_df = raw_df.select(from_json(col("value").cast("string"), schema).alias("data"))
expanded_df = json_df.selectExpr("explode(data) as record").select("record.*")


# start streaming
query = (
    expanded_df
    .writeStream.foreachBatch(process_batch)
    .option("checkpointLocation", "checkpoint_bot_filter")
    .start()
)

query.awaitTermination()
