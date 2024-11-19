from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, explode
from pyspark.sql.types import ArrayType, StructType, StructField, StringType, IntegerType, BooleanType, LongType


spark = SparkSession.builder.appName("WikipediaBotFilter").getOrCreate()

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

raw_df = (spark
          .readStream
          .format("socket")
          .option("host", "localhost")
          .option("port", 5050)
          .load())

# Parse the list of JSON objects and then explode it into individual records
json_df = raw_df.select(from_json(col("value"), schema).alias("data"))
expanded_df = json_df.select(explode(col("data")).alias("record")).select("record.*")

# Global variables to keep track of accumulated records
accumulated_df = None
total_records = 0
number_of_files = 0


def process_batch(df, epoch_id):
    global accumulated_df, total_records, number_of_files
    batch_count = df.count()
    total_records += batch_count

    accumulated_df = accumulated_df.union(df) if accumulated_df else df

    # Check if total_records reached 1,000
    if total_records >= 1000:
        number_of_files += 1
        # Write the accumulated records to CSV
        accumulated_df.coalesce(1).write.mode('append').csv('sample_data')

        # Reset counters and accumulated DataFrame
        total_records = 0
        accumulated_df = None

        if number_of_files == 40:
            query.stop()


# Start streaming and use foreachBatch to process data in batches
query = (expanded_df
         .filter("id % 100 < 20")
         .writeStream
         .foreachBatch(process_batch)
         .option("checkpointLocation", "checkpoint")
         .start())

query.awaitTermination()
