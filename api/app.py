import celery.states as states
from flask import Flask, json, url_for, jsonify, render_template, request
from worker import celery
from werkzeug.utils import secure_filename
import os
import time
import datetime
import hashlib
import mmap
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import mimetypes
from flask_bootstrap import Bootstrap
import pathlib
from time import time

# instantiate the extensions
bootstrap = Bootstrap()

dev_mode = True
app = Flask(
    __name__,
    template_folder="client/templates",
    static_folder="client/static",
)

app.config.update(
    TESTING=dev_mode,
    DEBUG=dev_mode,
    USE_RELOADER=dev_mode,
    THREADED=False,
    WTF_CSRF_ENABLED=True,
    REDIS_URL=os.environ.get('CELERY_RESULT_BACKEND'),
    QUEUES=["default"],
    TTL=30,
    PROPAGATE_EXCEPTIONS=True,
    JSON_SORT_KEYS=False,
    MAX_TIME_TO_WAIT=10,
    TASKS=['Short task', 'Long task', 'Task raises error']
)

# set config
app_settings = os.getenv("APP_SETTINGS")
app.config.from_object(app_settings)

# set up extensions
bootstrap.init_app(app)

BUCKET = os.environ['S3_BUCKET']
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCCESS_KEY = os.environ['AWS_SECRET_ACCCESS_KEY']
AWS_REGION = os.environ['AWS_REGION']
UPLOAD_FOLDER = '/uploads'
ACCEPTED_FILE_TYPES = os.environ['ACCEPTED_FILE_TYPES']

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


# upload the file to S3
@app.route("/log", methods=["POST"])
def upload_file():
    """
    Function to upload a file to an S3 bucket
    """
    if 'log_file' not in request.files:
        response = 'no file'

    file = request.files['log_file']
    start_time = round(time() * 1000)
    file_name = str(start_time) + secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, file_name)

    # start time to calculate the total processing time 
    mac = request.headers['X-Device-Mac']
    restaurant_code = request.headers['X-Restaurant-Code']
    file_save_time = ''
    today = datetime.date.today()

    # some file type do not provide file extension
    type = mimetypes.guess_type(file_path)
    mime_type = type[0]

    # for them need to create custom mime type info from their file extension
    if mime_type == None:
        _, file_extension = os.path.splitext(file_path)
        m_type = file_extension.split(".")[-1]
        mime_type = "application/" + m_type
    else:
        temp = mime_type.split("/")
        m_type = temp[1]

    # put constraint for file type allow [.txt, .zip, .log, .gzip, .gz, .csv]
    if m_type not in ACCEPTED_FILE_TYPES:
        write_error_log_s3(mime_type + " not accepted", mac)
        response = [mime_type + " type file not accepted"]
        response_object = {
            "status": "failure",
            "data": {
                "message": response
            }
        }
        return jsonify(response_object), 400

    # except
    try:
        file.save(file_path)
        os.chown(file_path, 1000, 1000)
        os.chmod(file_path, 0o777)
        # time taken to save into EFS
        file_save_time = str(int(round(time() * 1000)) - int(start_time))

        # find hash of the file
        hash_of_file = sha256sum(file_path)

    except ClientError as e:
        write_error_log_s3(str(e), mac)
        response = [str(e)]
        response_object = {
            "status": "failure",
            "data": {
                "message": response
            }
        }
        return jsonify(response_object), 400

        # verify de-duplication within 24 hours
    try:
        start_time_de_duplication = round(time() * 1000)
        dynamodb = boto3.client('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID,
                                aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
        # dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
        # table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

        # response = table.get_item(            
        #     Key={
        #         'task_id' : task_id,
        #         'mac' : 'AA-00-04-00-XX-YX'
        #     }
        # )

        response = dynamodb.get_item(
            TableName=os.environ['DYNAMODB_TABLE'],
            Key={
                'created_date': {'S': str(today)},
                'hash_of_file': {'S': str(hash_of_file)}
            }
        )

        # need to check if this is from same MAC address
        if 'Item' in response:
            mac_id = response['Item']['info']['M']['mac']['S']

            if mac_id == mac:
                os.remove(file_path)

                response = f"Duplicate attempt. This file already uploaded today."
                response_object = {
                    "status": "Failure",
                    "data": {
                        "message": response
                    }
                }
                return jsonify(response_object), 202

    except ClientError as e:
        write_error_log_s3(str(e), mac)
        response = [str(e)]
        response_object = {
            "status": "failure",
            "data": {
                "message": response
            }
        }
        return jsonify(response_object), 400

    de_duplication_time = str(int(round(time() * 1000)) - int(start_time_de_duplication))

    start_time_celery_task_creation = round(time() * 1000)
    celery_task_creation_time = str(int(round(time() * 1000)) + 100 - int(start_time_celery_task_creation))
    # queue has been saved actula upload will be done from queue
    task = celery.send_task('tasks.upload', args=[
        hash_of_file,
        file_path,
        file_name,
        mac,
        restaurant_code,
        file_save_time,
        mime_type,
        de_duplication_time,
        celery_task_creation_time
    ], kwargs={})

    # if sqs fail remove the file from EFS
    if task.id == None:
        os.remove(file_path)
        response = f"File not uploaded."
        # have to write inot log

    else:
        response = f"<a href='{url_for('check_task', task_id=task.id, external=True)}'>file successfully uploaded check status of {task.id} </a>"

    response_object = {
        "status": "success",
        "data": {
            "message": response,
            "task_id": task.id
        }
    }
    return jsonify(response_object), 202


# calculate the hash of a file
def sha256sum(filename):
    h = hashlib.sha256()
    with open(filename, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ) as mm:
            h.update(mm)
    return h.hexdigest()


# create a test task
@app.route("/task", methods=["POST"])
def run_task():
    try:
        task_type = request.form["type"]
        task = celery.send_task('tasks.create', args=[task_type], kwargs={})

        response_object = {
            "status": "success",
            "data": {
                "task_id": task.id
            }
        }
        return jsonify(response_object), 202
    except:
        return ("Test task not created")


# get all tasks
@app.route("/all_tasks", defaults={'date': None}, methods=["get"])
@app.route("/all_tasks/<date>", methods=["get"])
def get_all_tasks(date=None):
    try:
        # db = current_app.db
        # # col = db.collection_names()

        # # Collection name  
        # record_count = db.logs.find().count()
        tasks = []

        try:
            dynamodb = boto3.client('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID,
                                    aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
            # dynamodb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")
        except:
            return "dynamodb not able to connect"

        if date != None:
            tasks = dynamodb.query(
                TableName=os.environ['DYNAMODB_TABLE'],
                KeyConditionExpression='created_date = :created_date',
                ExpressionAttributeValues={
                    ':created_date': {'S': date}
                }
            )

        else:
            tasks = dynamodb.scan(
                TableName=os.environ['DYNAMODB_TABLE']
            )

        if tasks:
            tasks_result = []
            for task in tasks['Items']:
                tasks_result.append(task['created_date']['S'] + '::' + task['info']['M']['task_id']['S'])

            response_object = {
                "status": "success",
                "data": {
                    "total": len(tasks_result),
                    "tasks": tasks_result
                }
            }
            return jsonify(response_object), 202
        else:
            return jsonify("no result found"), 400

    except ClientError as e:
        return str(e)


@app.route("/all_tasks/mac/<mac>", methods=["get"])
def get_all_tasks_by_mac(mac):
    try:
        # db = current_app.db
        # # col = db.collection_names()

        # # Collection name  
        # record_count = db.logs.find().count()
        tasks = []

        try:
            dynamodb = boto3.client('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID,
                                    aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
            # dynamodb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")
        except:
            return "dynamodb not able to connect"

        tasks = dynamodb.scan(
            TableName=os.environ['DYNAMODB_TABLE']
        )

        if tasks:
            tasks_result = []
            for task in tasks['Items']:
                if task['info']['M']['mac']['S'] == mac:
                    tasks_result.append(task['created_date']['S'] + '::' + task['info']['M']['task_id']['S'])

            response_object = {
                "status": "success",
                "data": {
                    "total": len(tasks_result),
                    "tasks": tasks_result
                }
            }
            return jsonify(response_object), 202
        else:
            return jsonify("no result found"), 400

    except ClientError as e:
        return str(e)


@app.route("/all_tasks/restaurant_code/<restaurant_code>", methods=["get"])
def get_all_tasks_by_restaurant_code(restaurant_code):
    try:
        # db = current_app.db
        # # col = db.collection_names()

        # # Collection name  
        # record_count = db.logs.find().count()
        tasks = []

        try:
            dynamodb = boto3.client('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID,
                                    aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
            # dynamodb = boto3.resource('dynamodb', endpoint_url="http://localhost:8000")
        except:
            return "dynamodb not able to connect"

        tasks = dynamodb.scan(
            TableName=os.environ['DYNAMODB_TABLE']
        )

        if tasks:
            tasks_result = []
            for task in tasks['Items']:
                if task['info']['M']['restaurant_code']['S'] == restaurant_code:
                    tasks_result.append(task['created_date']['S'] + '::' + task['info']['M']['task_id']['S'])

            response_object = {
                "status": "success",
                "data": {
                    "total": len(tasks_result),
                    "tasks": tasks_result
                }
            }
            return jsonify(response_object), 202
        else:
            return jsonify("no result found"), 400

    except ClientError as e:
        return str(e)


@app.route("/", methods=["GET"])
def home():
    return render_template("main/home.html")


@app.route("/tasks", methods=["GET"])
def get_task():
    return render_template("main/tasks.html")


# get task details from created_date and task_id
@app.route("/tasks/<task>", methods=["GET"])
def get_status(task):
    try:
        dynamodb = boto3.client('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID,
                                aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
        # table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

        date = task[:10]
        task_id = task[10:]

        response = dynamodb.query(
            TableName=os.environ['DYNAMODB_TABLE'],
            KeyConditionExpression='created_date = :created_date',
            ExpressionAttributeValues={
                ':created_date': {'S': date}
            }
        )

        response_object = {"status": "error"}
        if response and response['Count'] > 0:
            for task in response['Items']:
                if task['info']['M']['task_id']['S'] == task_id:
                    start_time = task['info']['M']['start_time']['S']
                    end_time = task['info']['M']['end_time']['S']
                    dt1 = datetime.datetime.fromtimestamp(int(start_time) / 1000)
                    dt2 = datetime.datetime.fromtimestamp(int(end_time) / 1000)
                    file_save_time = task['info']['M']['file_save_time']['S'] if task['info']['M']['file_save_time'][
                        'S'] else 'less than 1'

                    t1 = str(datetime.datetime.strptime(str(dt1)[0:19], "%Y-%m-%d  %H:%M:%S"))
                    t2 = str(datetime.datetime.strptime(str(dt2)[0:19], "%Y-%m-%d  %H:%M:%S"))
                    file_size = (int(task['info']['M']['file_size']['S']) / 1024) / 1024
                    hash_of_file = task['hash_of_file']['S']
                    actual_time_taken_sec = (dt2 - dt1).total_seconds()
                    actual_time_taken_min = 0
                    actual_time_taken = ''
                    if actual_time_taken_sec > 60:
                        actual_time_taken_min = actual_time_taken_sec / 60
                        actual_time_taken_sec = actual_time_taken_sec % 60
                        actual_time_taken = str(actual_time_taken_min) + ' min '
                    elif actual_time_taken_sec < 1:
                        actual_time_taken = str(int(actual_time_taken_sec * 1000)) + ' ms' 
                    else:
                        actual_time_taken += str(actual_time_taken_sec) + ' sec' 

                    response_object = {
                        "status": "success",
                        "data": {
                            "created_date": date,
                            "task_id": task_id,
                            "hash_of_file": hash_of_file,
                            "mac": task['info']['M']['mac']['S'],
                            "restaurant_code": task['info']['M']['restaurant_code']['S'],
                            "file_name": task['info']['M']['file_name']['S'],
                            "file_size": f'{file_size:.2f}' + ' MB',
                            "start_time": t1,
                            "end_time": t2,
                            "time_taken": actual_time_taken,
                            "s3_path": task['info']['M']['s3_path']['S'],
                            "file_save_time_to_efs": file_save_time + ' ms',
                            "de_duplication_time": task['info']['M']['de_duplication_time']['S'] + ' ms',
                            "celery_task_creation_time": task['info']['M']['celery_task_creation_time']['S'] + ' ms',
                            "dynamo_db_worker_time": task['info']['M']['dynamo_db_worker_time']['S'] + ' ms',
                            "s3_upload_time": task['info']['M']['s3_upload_time']['S'] + ' ms',
                        }
                    }

        return jsonify(response_object)

    except ClientError as e:
        response_object = {"status": str(e)}
        return jsonify(response_object)


# get task status for test tasks
@app.route("/task_status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    task = celery.AsyncResult(task_id)

    if task.state == states.PENDING:
        state = task.state
    else:
        state = str(task.result)

    if task:
        response_object = {
            "status": "success",
            "data": {
                "task_id": task.id,
                "task_status": state
            },
        }
    else:
        response_object = {"status": "error"}
    return jsonify(response_object)


# this will upload a error log file
def write_error_log_s3(error, mac):
    s3_client = boto3.client('s3', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
    file_name = str(round(time() * 1000)) + '.txt'
    object = mac + '/error_logs/' + file_name

    f = open(file_name, "w")
    f.write(error)
    f.close()

    try:
        s3_client.upload_file(file_name, BUCKET, object)

        SUBJECT = "Log Upload S3 Application Error"
        BODY_TEXT = BUCKET + '/' + object
        BODY_HTML = "<h2>Eorror in Log Upload to S3 Application</h2>" + BODY_TEXT
        CHARSET = "UTF-8"
        ses_client = boto3.client('ses', region_name=AWS_SES_REGION, aws_access_key_id=AWS_SES_ACCESS_KEY_ID,
                                  aws_secret_access_key=AWS_SES_SECRET_ACCESS_KEY)
        try:
            # Provide the contents of the email.
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

            print(jsonify(response))
        # Display an error if something goes wrong. 
        except ClientError as e:
            return False

        return True
    except ClientError as e:
        return False


@app.route('/add/<int:param1>/<int:param2>')
def add(param1: int, param2: int) -> str:
    task = celery.send_task('tasks.add', args=[param1, param2], kwargs={})
    response = f"<a href='{url_for('check_task', task_id=task.id, external=True)}'>check status of {task.id} </a>"
    return response


@app.route('/check/<string:task_id>')
def check_task(task_id: str) -> str:
    res = celery.AsyncResult(task_id)
    if res.state == states.PENDING:
        return res.state
    else:
        return str(res.result)


@app.route('/health_check')
def health_check() -> str:
    return jsonify("OK")


@app.route('/efs_files')
def dump_efs_files():
    # efs_client = boto3.client('efs', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCCESS_KEY)
    files = os.listdir(UPLOAD_FOLDER)
    life_span = int(os.environ['EFS_FILE_LIFE_SPAN_IN_HOURS'])
    day_secs = float(60 * 60 * life_span)
    result = []
    for file in files:
        fname = pathlib.Path(UPLOAD_FOLDER + '/' + file)
        mtime = datetime.datetime.fromtimestamp(fname.stat().st_mtime)
        ctime = datetime.datetime.fromtimestamp(fname.stat().st_ctime)

        # remove the file it is more than 24 hours 
        laps = time() - fname.stat().st_ctime
        if laps > day_secs:
            os.remove(UPLOAD_FOLDER + '/' + file)
        else:
            result.append({'file': file, 'created': ctime, 'modified': mtime})

    response_object = {
        "status": "If any files created more than " + str(
            life_span) + " hours ago, removed. Rest of them are in listing.",
        "data": {
            "result": result
        },
    }
    return jsonify(response_object)


# this function will query a json dict
# j = json dict, s = search key, v = value to match with [op]
def get_val(j, s, v=None):
    for k in j:
        if v == None and k == s:
            return j[k]
        elif v != None and k == s and v == j[k]:
            return True
        elif v != None and k == s and v != j[k]:
            return False
        elif isinstance(j[k], dict):
            return get_val(j[k], s, v)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port='5000')
