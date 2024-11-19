### Step 1: Run Real-Time Wikipedia Edit Streamer with TCP Socket Output


```commandline
python hw2/stream.py 20241025
```

### Step 2: Sample data using Spark Streaming and save it to csv files

```commandline
cd hw2
python sample_stream.py
```

### Step 3: Make EDA and Modelling to train model
[Look at this notebook for details](Bloom%20FIlter%20and%20EDA.ipynb)

### Step 4: Implement Online Inference pipeline using Spark streaming
```commandline
# to run kafka
docker-compose up
# run producer
python kafka_stream.py
# run spark streaming
python online_inference
```
![img.png](images/img.png)

### Summary
We implemented a scalable pipeline to filter out bots from Wikipedia Edits stream. 

We used BloomFilter to filter out 90% of edits and our model to find bots and add them to the black list. 
As we can see, with each run our black list becomes larger, as well as our ability to detect bots.