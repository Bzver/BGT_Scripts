# import tensorflow as tf

# gpus = tf.config.list_physical_devices('GPU')
# print("Num GPUs Available: ", len(gpus))
# print("List of GPUs: ", gpus)

# print(tf.__version__)

import tensorflow as tf
import os # Import the os module

# Print the environment variable value
print("TF_CPP_MIN_LOG_LEVEL:", os.environ.get('TF_CPP_MIN_LOG_LEVEL'))

print("TF Version:", tf.__version__)
gpus = tf.config.list_physical_devices('GPU')
print("GPUs Found:", gpus)
if gpus:
    print("Trying GPU operation...")
    try:
        tf.random.set_seed(1234)
        with tf.device('/GPU:0'):
            a = tf.random.normal((100, 100))
            b = tf.random.normal((100, 100))
            c = tf.matmul(a, b)
        print("GPU operation successful. Result on:", c.device)
    except Exception as e:
        print("!!! Error during GPU operation:", e)
else:
    print("No GPU found by TensorFlow.")
