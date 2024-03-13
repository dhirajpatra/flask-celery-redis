import os
from os import name
import time
import datetime
from celery import Celery
import boto3
from boto3.s3.transfer import TransferConfig, S3Transfer
from botocore.exceptions import ClientError, ParamValidationError 
from urllib.parse import quote_plus
from time import time

# sqs endpoint
endpoint_url = 'sqs://{}:{}@'.format(
    quote_plus(os.environ.get('AWS_ACCESS_KEY_ID')),
    quote_plus(os.environ.get('AWS_SECRET_ACCCESS_KEY'))
)

# CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379'),
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', endpoint_url),
# CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis-prod:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

BUCKET = os.environ['S3_BUCKET']
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCCESS_KEY = os.environ['AWS_SECRET_ACCCESS_KEY']
AWS_REGION = os.environ['AWS_REGION']
# REGION = "us-west-1"
MB = 1024
GB = MB ** 3
MAX_CONCURRENCY = os.environ['MAX_CONCURRENCY']

EMAIL_HOST = 'email-smtp.us-east-1.amazonaws.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
AWS_SES_ACCESS_KEY_ID = os.environ['AWS_SES_ACCESS_KEY_ID']
AWS_SES_SECRET_ACCESS_KEY = os.environ['AWS_SES_SECRET_ACCESS_KEY']
EMAIL_HOST_USER = os.environ['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
AWS_SES_REGION = 'us-east-1'
# Amazon SES credentials
# The keys are the same used for menu editor

EMAIL_BACKEND = 'elacarte.email.backends.EmailBackend'

# Ajax uploader expects these values to be set to blank at least.
# For more info read https://github.com/goodcloud/django-ajax-uploader/
# This is probably an issue with the ajaxuploader.
# https://github.com/GoodCloud/django-ajax-uploader/blob/master/ajaxuploader/views/s3.py#L10-L19
AWS_UPLOAD_CLIENT_KEY = ''
AWS_UPLOAD_CLIENT_SECRET_KEY = ''

DEFAULT_FROM_EMAIL = 'noreply@prestotablet.com'

DAY_ROLLOVER_HOUR = 4
RECIPIENT = 'infra@elacarte.com'
ALERT_EMAIL_SENDER = 'alerts@prestotablet.com'
ALERT_WEBSERVICE_STATUS_URL = 'https://webservice.elacarte.com'
ALERT_WEBSERVICE_AUTH = ('Alerts', '8J78lbJtCzDCyNz8Aw9sMtSw4xOJ95An')
OPS_EMAIL_ACCOUNT = 'ops@elacarte.com'

RECEIPT_EMAIL_SENDER = 'receipts@prestotablet.com'
RECEIPT_EMAIL_REPLYTO = 'feedback@elacarte.com'
PRESTOGRAM_EMAIL_SENDER = 'prestogram@prestotablet.com'
PRESTOGRAM_EMAIL_REPLYTO = 'no-reply@elacarte.com'


@celery.task(name='tasks.add')
def add(x: int, y: int) -> int:
    time.sleep(5)
    return x + y

@celery.task(name='tasks.create')
def create(task_type):
    time.sleep(task_type * 5)
    return True

# actul uploading to s3
@celery.task(name='tasks.upload', bind=True)
def upload(self, hash_of_file, file_path, file_name, mac, restaurant_code, file_save_time, mime_type,de_duplication_time, celery_task_creation_time):
    try:
        start_time_s3 = round(time() * 1000)
        s3_client = False
        s3_client = boto3.client('s3', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
        config = TransferConfig(multipart_threshold=25 * MB, 
            max_concurrency=int(MAX_CONCURRENCY),
            multipart_chunksize=25 * MB, 
            use_threads=True,
            num_download_attempts=10)
        # remove time stamp from file name to extract the actual file name        
        actual_file_name = file_name[13:]
        start_time = file_name[0:13]
        object = mac + '/' + actual_file_name
        file_size = os.stat(file_path).st_size


        s3_client.upload_file(
            file_path, 
            BUCKET, 
            object, 
            ExtraArgs={
                'ContentType': mime_type
                },
                Config=config
                ) 
        end_time_s3 = str(int(round(time() * 1000)) - int(start_time_s3))

        try:
            # save into database
            # {
            #   "created_date": "2020-12-09",
            #   "hash_of_file": "b7bda0a3f55b142dde96ea82b12934f9bcf38b7c86ad68773067133a435d76ba",
            #   "info": {
            #     "application_name": "testing application",
            #     "application_type": "test",
            #     "end_time": "1607521271566",
            #     "file_name": "Itsycal.zip",
            #     "file_save_time": "1",
            #     "file_size": "778369",
            #     "mac": "AA:XX:XX:YY:YY",
            #     "restaurant_code": "test1234",
            #     "s3_path": "https://presto-infra-staging-test-logs.s3-us-west-2.amazonaws.com/AA:XX:XX:YY:YY/Itsycal.zip",
            #     "start_time": "1607521260829",
            #     "task_id": "9ce3f460-bd23-45ef-9d7f-7c35f4b38be1"
            #   }
            # }
            start_time_dynamo_db_worker = round(time() * 1000)
            # get current job details
            job = self.request
            
            # db = current_app.db
            dynamodb = boto3.client('dynamodb',  region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
            s3_path = 'https://' + BUCKET + '.s3-' + os.environ['AWS_REGION'] + '.amazonaws.com/' + object
            end_time = round(time() * 1000)
            today = datetime.date.today()
            end_time_dynamo_db_worker = str(int(round(time() * 1000)) + 100 - int(start_time_dynamo_db_worker))

            post = {
                      "created_date": {
                        "S": str(today)
                      },
                      "info": {
                        "M": {
                          "task_id": {
                            "S": job.id
                            },
                          "end_time": {
                            "S": str(end_time)
                          },
                          "file_name": {
                            "S": actual_file_name
                          },
                          "file_save_time": {
                            "S": file_save_time
                          },
                          "file_size": {
                            "S": str(file_size)
                          },
                          "mac": {
                            "S": mac
                          },
                          "restaurant_code": {
                            "S": restaurant_code
                          },
                          "s3_path": {
                            "S": s3_path
                          },
                          "start_time": {
                            "S": start_time
                          },
                          "de_duplication_time": {
                            "S": de_duplication_time
                          },
                          "celery_task_creation_time": {
                            "S": celery_task_creation_time
                          },
                          "dynamo_db_worker_time": {
                            "S": end_time_dynamo_db_worker
                          },
                          "s3_upload_time": {
                            "S": end_time_s3
                          },
                        }
                      },
                      "hash_of_file": {
                        "S": hash_of_file
                      }
                    }
            
            dynamodb.put_item(
                TableName=os.environ['DYNAMODB_TABLE'],
                Item=post
            )
            # db.logs.insert_one(post)

            # remove the file from EFS
            remove_file(mac, file_path)

        except ClientError as e:
            # remove failed job
            # q = Queue()
            # registry = FailedJobRegistry(queue=q)
            # for job_id in registry.get_job_ids():
            #     registry.remove(job_id, delete_job=True)
            try:
                os.remove(file_path)         
            except ClientError as e:
                write_error_log_s3(str(e), mac)
            return False 
        
    except ClientError as e:
        write_error_log_s3(str(e), mac)
        return False 
    except ParamValidationError as e:
        write_error_log_s3(str(e), mac)
        return False    

    return True


# this will remove file from EFS or intermidiatary place as a task
def remove_file(mac, file_path):
    try:
        os.chmod(file_path, 0o777)
        os.remove(file_path)         
    except ClientError as e:
        write_error_log_s3(str(e), mac)
        return False 


# this will upload a error log file
def write_error_log_s3(error, mac):
    s3_client = boto3.client('s3', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
    file_name = str(round(time() * 1000)) + '.txt' 
    object = mac + '/error_logs/' + file_name
    
    f = open(file_name, "w")
    f.write(error)
    f.close()

    try:
        s3_client.upload_file(file_name, BUCKET, object)
        os.remove(file_name)

        SUBJECT = "Log Upload S3 Application Error"
        BODY_TEXT = BUCKET + '/' + object
        BODY_HTML = "<h2>Eorror in Log Upload to S3 Application</h2>" + BODY_TEXT
        CHARSET = "UTF-8"
        ses_client = boto3.client('ses',region_name=AWS_REGION, aws_access_key_id=AWS_SES_ACCESS_KEY_ID, aws_secret_access_key=AWS_SES_SECRET_ACCESS_KEY)
        try:
            #Provide the contents of the email.
            response = ses_client.send_email(
                Destination={
                    'ToAddresses': [
                        RECIPIENT,
                    ],
                },
                Message={
                    'Body': {
                        'Html': {
                            'Charset': CHARSET,
                            'Data': BODY_HTML,
                        },
                        'Text': {
                            'Charset': CHARSET,
                            'Data': BODY_TEXT,
                        },
                    },
                    'Subject': {
                        'Charset': CHARSET,
                        'Data': SUBJECT,
                    },
                },
                Source=ALERT_EMAIL_SENDER,
                # If you are not using a configuration set, comment or delete the
                # following line
                # ConfigurationSetName=CONFIGURATION_SET,
            )
        # Display an error if something goes wrong. 
        except ClientError as e:
            return False

        return True
    except ClientError as e:
        return False