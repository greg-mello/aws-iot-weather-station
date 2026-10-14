import glob
import time
import random
import math
import json
from awscrt import mqtt
from awsiot import mqtt_connection_builder
from awsiot import iotshadow

# AWS IoT configuration
ENDPOINT = "azcbnm85hfmcc-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "pi_weather_monitor"
PATH_TO_CERT = "certificates/f6aff737f52d0068f29c96f385597e885e77aee24c1e30b35b018baa155d53d5-certificate.pem.crt"
PATH_TO_KEY = "certificates/f6aff737f52d0068f29c96f385597e885e77aee24c1e30b35b018baa155d53d5-private.pem.key"
PATH_TO_ROOT = "certificates/AmazonRootCA1.pem"
TOPIC_TELEMETRY = "weather/readings"
TOPIC_CONFIG = "weather/config"

# default config, pre-shadow
config = {
    'reading_interval': 5,
    'humidity_enabled': True,
    'pressure_enabled': True
}

# code for the new sensor that only does temperature
base_dir = "/sys/bus/w1/devices/"
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'

# get the raw temperature from the sensor
def read_temp_raw():
    with open(device_file, 'r') as f:
        lines = f.readlines()
    return lines

# convert the raw temperature
def read_temperature():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
# convert to Fahrenheit
        temp_f = (temp_c * 9/5) + 32
        return round(temp_f, 2)
    return None

# function to simulate humidity with a random range of 20-80%
def simulate_humidity():
    base_humidity = 50
    time_factor = time.time() / 7200  
    trend = math.sin(time_factor) * 15
    noise = random.uniform(-3, 3)
    humidity = base_humidity + trend + noise
    return round(max(20, min(80, humidity)), 2)

# function to simulate barometric pressure with a range of 980-1050 hPa
def simulate_pressure():
    base_pressure = 1013.25
    time_factor = time.time() / 3600
    trend = math.sin(time_factor) * 15
    noise = random.uniform(-2, 2)
    pressure = base_pressure + trend + noise
    return round(pressure, 2)

# create a dictionary of readings that can be output to AWS IoT
def get_weather_reading():
    data = {
        'temperature': read_temperature(),
        'timestamp': int(time.time())
    }
    
# only include humidity if it is set to enabled
    if config['humidity_enabled']:
        data['humidity'] = simulate_humidity()
    
# only include pressure if it is set to enabled
    if config['pressure_enabled']:
        data['pressure'] = simulate_pressure()
    
    return data

# confirmation of shadow instructions
def on_message_received(topic, payload, **kwargs):
    print(f"Received config message: {payload}")

# callback of shadow commit
def on_shadow_delta_updated(delta):
    global config
    print(f"Shadow update received: {delta.state}")
    
# update configurations from shadow
    if 'reading_interval' in delta.state:
        config['reading_interval'] = delta.state['reading_interval']
        print(f"Reading interval changed to: {config['reading_interval']} seconds")
    if 'humidity_enabled' in delta.state:
        config['humidity_enabled'] = delta.state['humidity_enabled']
        print(f"Humidity sensor: {'enabled' if config['humidity_enabled'] else 'disabled'}")
    if 'pressure_enabled' in delta.state:
        config['pressure_enabled'] = delta.state['pressure_enabled']
        print(f"Pressure sensor: {'enabled' if config['pressure_enabled'] else 'disabled'}")
    
    print(f"Current configuration: {config}")

# AWS IoT section
if __name__ == "__main__":

# establish MQTT connection
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=ENDPOINT,
        cert_filepath=PATH_TO_CERT,
        pri_key_filepath=PATH_TO_KEY,
        ca_filepath=PATH_TO_ROOT,
        client_id=CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30
    )
    
    print(f"Connecting to AWS IoT...")
    connect_future = mqtt_connection.connect()
    connect_future.result()
    print("Connected to AWS IoT Core!")

# establish shadow client
    shadow_client = iotshadow.IotShadowClient(mqtt_connection)
    
# subscribe to shadow updates
    delta_subscribed_future, _ = shadow_client.subscribe_to_shadow_delta_updated_events(
        request=iotshadow.ShadowDeltaUpdatedSubscriptionRequest(thing_name=CLIENT_ID),
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_shadow_delta_updated
    )
    delta_subscribed_future.result()
    print("Subscribed to shadow delta updates")
    
# subscribe to configuration topic
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=TOPIC_CONFIG,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received
    )
    subscribe_future.result()
    print(f"Subscribed to {TOPIC_CONFIG}")
    
    try:
        while True:
            data = get_weather_reading()
            message = json.dumps(data)
            
            mqtt_connection.publish(
                topic=TOPIC_TELEMETRY,
                payload=message,
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            print(f"Published: {message}")
            time.sleep(config['reading_interval'])
            
    except KeyboardInterrupt:
        print("\nDisconnecting...")
        disconnect_future = mqtt_connection.disconnect()
        disconnect_future.result()
        print("Disconnected!")