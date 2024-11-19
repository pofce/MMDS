from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, explode
from pyspark.sql.types import StructType, StructField, StringType, LongType, IntegerType, BooleanType, ArrayType
from pyspark.ml import PipelineModel
import pickle
import os


# 1. Initialize Spark Session
spark = SparkSession.builder \
    .appName("WikipediaBotFilterStreaming") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# 2. Define the Schema
schema = ArrayType(StructType([
    StructField("id", LongType(), True),
    StructField("title", StringType(), True),
    StructField("user", StringType(), True),
    StructField("bot", BooleanType(), True),
    StructField("length", IntegerType(), True),
    StructField("wiki", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("minor", BooleanType(), True),
    StructField("comment", StringType(), True),
]))

# 3. Load the Pre-trained Model
model_save_path = "/Users/dmytro.miedviediev/Projects/MMDS/hw2/model/"
model = PipelineModel.load(model_save_path)

# Initialize or Load the Bloom Filter
bloom_filter_path = "bloom_filter.pkl"


if os.path.exists(bloom_filter_path):
    with open(bloom_filter_path, "rb") as f:
        state = pickle.load(f)
    bloom_filter = BloomFilter.from_state(state)
    print(f"Loaded existing Bloom filter with {len(bloom_filter)} entries.")
else:
    # Initialize a new Bloom Filter with expected items and false positive rate
    expected_items = 1000000  # Adjust based on your requirements
    false_positive_rate = 0.001  # Adjust based on your tolerance for false positives
    bloom_filter = BloomFilter(expected_items, false_positive_rate)
    print("Initialized a new Bloom filter.")

# 5. Read and Parse Streaming Data
raw_df = spark.readStream \
    .format("socket") \
    .option("host", "localhost") \
    .option("port", 5050) \
    .load()

json_df = raw_df.select(from_json(col("value"), schema).alias("data"))
expanded_df = json_df.select(explode(col("data")).alias("record")).select("record.*")


# 6. Define the Batch Processing Function
def process_batch(batch_df, epoch_id):
    global bloom_filter

    if batch_df.rdd.isEmpty():
        print(f"Epoch {epoch_id}: Empty batch.")
        return

    # Apply the pre-trained model to make predictions
    predictions = model.transform(batch_df)

    # Assuming the model adds a 'prediction' column where 1.0 indicates a bot
    bots_df = predictions.filter(col("prediction") >= 0.5)

    # Collect the IDs of bot records
    bot_ids = [row.id for row in bots_df.select("id").collect()]

    # Update the Bloom filter with the new bot IDs
    for bot_id in bot_ids:
        bloom_filter.add(bot_id)

    # Optionally, save the Bloom filter periodically
    if epoch_id % 100 == 0:
        with open("bloom_filter.pkl", "wb") as f:
            pickle.dump(bloom_filter, f)
        print(f"Epoch {epoch_id}: Bloom filter saved with {len(bloom_filter)} entries.")

    # Print status
    print(
        f"Epoch {epoch_id}: Processed batch with {len(bot_ids)} bot records. Total bloom filter size: {len(bloom_filter)}")


# 7. Start the Streaming Query
query = expanded_df \
    .filter("id % 100 < 20") \
    .writeStream \
    .foreachBatch(process_batch) \
    .option("checkpointLocation", "checkpoint_bot_filter") \
    .start()

query.awaitTermination()
