import json
import boto3
import email
from email.policy import default
from util import one_hot_encode, vectorize_sequences
import numpy as np
import time
import os

vocabulary_length = 9013


def lambda_handler(event, context):
    # TODO implement
    
    ENDPOINT_NAME = os.environ['SAGEMAKER_ENDPOINT'] 
    
    object_s3_bucket = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']
    
    email_elements = get_content(object_s3_bucket, object_key)
    
    print('------')
    print(email_elements)
    print('------')
    
    
    email_elements['Result'], email_elements['Score'] = check_spam(email_elements, ENDPOINT_NAME)
    
    send_email(email_elements)
    
            
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

def check_spam(email_elements, ENDPOINT_NAME):
    
    payload = one_hot_encode([email_elements['Body']], vocabulary_length)
    payload = vectorize_sequences(payload, vocabulary_length)
    
    
    runtime= boto3.client('runtime.sagemaker')
    response = runtime.invoke_endpoint(EndpointName=ENDPOINT_NAME,
                                      ContentType='application/json',
                                      Body=json.dumps(payload.tolist()))
                
    response = json.loads(response["Body"].read().decode("utf-8"))
    
    score = response['predicted_probability'][0][0] * 100
    if response['predicted_label'][0][0] == 0:
        score = 100 - score
    result = 'Spam' if response['predicted_label'][0][0] == 1 else 'Ham'

    
    return result, score

def send_email(email_elements):
    
    ses_client = boto3.client('ses')
    
    
    email_plaintxt = f"""
    We received your email sent at {email_elements['Date']} with the subject {email_elements['Subject']}. \n
    Here is a 240 character sample of the email body: {email_elements['Body'][:240]} \n
    The email was categorized as {email_elements['Result']} with a {email_elements['Score']}% confidence.\n
    """
    
    message={"Body": {  "Text": {"Charset": "UTF-8", "Data": email_plaintxt,}},
                        "Subject": {"Charset": "UTF-8","Data": f"Spam check of {email_elements['Subject']}",},}
    
    destination = {"ToAddresses": [email_elements['From'],],}
    
    ses_client.send_email(Destination=destination, Message=message, Source=email_elements['To'])
    
    return
    
    


def get_content(bucketname, key):
    
    email_elements = dict()
    
    s3client = boto3.client('s3')
    eml_object = s3client.get_object(
            Bucket=bucketname,
            Key=key)
            
    eml_str = eml_object['Body'].read().decode('utf-8') 
    
    message = email.message_from_string(eml_str, policy=default)
    
    email_elements['Subject'] = message['Subject']
    email_elements['Date'] = message['Date']
    email_elements['From'] = message['From'].addresses[0].username + '@' + message['From'].addresses[0].domain 
    email_elements['To'] = message['To'].addresses[0].username + '@' + message['To'].addresses[0].domain 

    while type(message) != type('str'):
        message = message.get_payload()
        if type(message) == type(['list']):
            message = message[0]
            
    
    email_elements['Body'] = message.strip()
    
    return email_elements