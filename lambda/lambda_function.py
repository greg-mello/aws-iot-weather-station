import boto3
import time
from datetime import datetime
from zoneinfo import ZoneInfo  # built-in in Python 3.9+

sns_client = boto3.client('sns')
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:206749730903:demo_topic"

# change from default timezone of UTC
LOCAL_TZ = ZoneInfo("America/New_York")

def lambda_handler(event, context):
    raw_message = event.get('message', 'No message received')

    formatted_message = f"DEMONSTRATION WEATHER ALERT\n\n{raw_message}"

    try:
        # split header and readings
        if ' - ' in raw_message:
            header, readings = raw_message.split(' - ', 1)
            reading_lines = readings.split(', ')

            # find and convert timestamp
            for i, line in enumerate(reading_lines):
                if line.lower().startswith('timestamp:'):
                    try:
                        # extract the epoch
                        ts = int(line.split(':', 1)[1].strip())

                        # convert to local timezone
                        local_dt = datetime.fromtimestamp(ts, tz=LOCAL_TZ)
                        formatted_ts = local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

                        reading_lines[i] = f"Timestamp: {formatted_ts}"
                    except Exception as e:
                        print("Timestamp conversion error:", e)
                        pass

            formatted_readings = '\n'.join(reading_lines)
            formatted_message = f"DEMONSTRATION WEATHER ALERT\n\n{header}\n{formatted_readings}"

    except Exception as e:
        print("Formatting error:", e)
        formatted_message = f"DEMONSTRATION WEATHER ALERT\n\n{raw_message}"

    # publish to SNS
    sns_client.publish(
        TopicArn=SNS_TOPIC_ARN,
        Message=formatted_message,
        Subject="Demo Weather Alert"
    )

    print("Email sent:\n", formatted_message)

    return {'statusCode': 200, 'body': 'Demo alert sent successfully!'}
