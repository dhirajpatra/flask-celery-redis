# Docker Flask Celery Redis SQS

This application will uplaod a log from any device and any size [now upto 5 GB]. It uses message queue, multipart, data forwarder technologies to make the application robust even in low internet connection.

## How to use

### Dashboard 
After running the application. Just open the browser and go to root you can see the details there.

### API
`curl --location --request POST 'http://localhost/log' \
--header 'X-Restaurant-Code: test1234' \
--header 'X-Device-Mac: AA:XM:XX:YY:ZZ' \
--header 'X-Requestor-Type: restaurant' \
--form 'log_file=@"/Users/dhirajpatra/Desktop/example_1.json"'`
