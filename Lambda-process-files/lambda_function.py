import boto3
import time 

et = boto3.client('elastictranscoder')
iam = boto3.client('iam')
s3 = boto3.client('s3')
ses = boto3.client('ses')
api = boto3.client('apigateway')
ssm = boto3.client('ssm')

#you can't alter these addresses without confirming them in SES first! 
source_email = "sjoerd.santema@sentia.com"
review_email = "sjoerdsantema@gmail.com"

def lambda_handler(event, context):
    #use our bucket from the cfn template
    response = s3.list_objects(Bucket='video-review-origin')
    #but first make sure the bucket is not empty
    try:
        contents = response['Contents']
    except KeyError:
        return
    #add all keys ending with mp4 to a list    
    keys = []
    for x in response['Contents']:
        key = x['Key']
        if key.endswith('mp4'):
            keys.append(x['Key'])
    #fish up the role we created in the cfn template
    roles = iam.list_roles()
    role_list = roles['Roles']
    for x in role_list:
        if "Transcoder_Role_Name" in  x['RoleName']:
            arn_role = x['Arn']
    #check if the pipeline exists 
    response = et.list_pipelines()
    pipeline_exists = "no"
    #iterate through all pipelines
    for x in response['Pipelines']:
        if x['Name'] == "video-review-temp-pipeline":
            pipeline_exists = "yes"
    #create pipeline if it wasnt found in our iterations
    if pipeline_exists == "no":
        response = et.create_pipeline(
        Name='video-review-temp-pipeline',
        InputBucket='video-review-origin',
        OutputBucket='non-approved-files',
        Role=arn_role
        )
        print("pipeline created because it wasnt there yet")
    #check if the preset exists and if not create it
    preset_exists = "no"
    response = et.list_presets()
    #iterate through all presets
    for x in response['Presets']:
        if x['Name'] == "video-review-preset":
            preset_exists = "yes"
            preset_id = x['Id']
    #create preset if it wasnt found in our iterations
    if preset_exists == "no":
        response = et.create_preset(
            Name='video-review-preset',
            Description='preset for thumbnail generation',
            Container='mp4',
                Video={
                    'Codec': 'H.264',
                    'CodecOptions': {
                        'Profile': 'main',
                        'Level': '3.1',
                        'MaxReferenceFrames': '3'
                    },
                    'KeyframesMaxDist': '90',
                    'FixedGOP': 'false',
                    'BitRate': '2200',
                    'FrameRate': '30',
                    'MaxWidth': '1280',
                    'MaxHeight': '720',
                    'DisplayAspectRatio': 'auto',
                    'SizingPolicy': 'ShrinkToFit',
                    'PaddingPolicy': 'NoPad',
                    },
                Thumbnails={
                    'Format': 'jpg',
                    'Interval': '99999',
                    'MaxWidth': '1280',
                    'MaxHeight': '720',
                    'SizingPolicy': 'ShrinkToFit',
                    'PaddingPolicy': 'NoPad'
                    }
            )
    #before we can create a job we need the id of the pipeline 
    response = et.list_pipelines(
    Ascending='false'
    )
    for x in response["Pipelines"]:
        c = x["Name"]
        if c == "video-review-temp-pipeline":
            pipeline_id=x["Id"]
            break
    #before we can create a job we need the id of the preset
    response = et.list_presets(
    Ascending='false'
    )
    for x in response["Presets"]:
        t = x["Name"]
        if t == "video-review-preset":
            preset_id=x["Id"]
            break
    #create a job for each entry in our keys list
    for x in keys:
        pn = x.rsplit('.', 1)
        pn = pn[0]
        timecode = str(time.time())
        timecode = str(timecode[0:6:1])
        response = et.create_job(
        PipelineId=pipeline_id,
        Inputs=[
            {
                'Key': x,
                'FrameRate': 'auto',
                'Resolution': 'auto',
                'AspectRatio': 'auto',
                'Interlaced': 'auto',
                'Container': 'auto'
            },
        ],
        Outputs=[
            {
                'Key': "videos/"+pn+"-"+timecode+".mp4",
                'ThumbnailPattern': 'thumbnails/{count}-thumbnail-'+pn+"-"+timecode,
                'Rotate': 'auto',
                'PresetId': preset_id
                }
        ] )
        #wait a few moments, file needs to be available first
        time.sleep(15)
        #generate a presigned url to use in e-mail
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket' : 'non-approved-files',
                'Key' : "videos/"+pn+"-"+timecode+".mp4"
            }
        )
        #we need to use variables below in link to api; reconstruct the links in approve_video.py
        origin_object_key = pn+"-"+timecode
        #lookup the api gateway id in ssm
        api_id = ssm.get_parameter(Name='api-id')
        api_id = api_id['Parameter']['Value']
        #generate a link to the api gateway endpoint to include in email
        region = "eu-west-1"
        link = "https://"+api_id+".execute-api."+region+".amazonaws.com/LATEST/approval?approval="+origin_object_key
        #compose message with presigned url for review and approval link
        response = ses.send_email(
            Destination={
                'BccAddresses': [
                ],
                'CcAddresses': [
                ],
                'ToAddresses': [
                    review_email
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': 'UTF-8',
                        'Data': "<h1>He there!</h1><b>It seems there is a new video review up for approval. Check it out!</b><br><a class=\"ulink\" href=\""+url+"\"target=\"_blank\">Click here for the video..</a><br><a class=\"ulink\" href=\""+link+"\"target=\"_blank\">Click here to approve this video</a>.",
                    },
                    'Text': {
                        'Charset': 'UTF-8',
                        'Data': "New video review ready for approval. Copy this link in the address bar of your browser to see the video:"+url,
                    },
                },
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': 'New video review ready for approval!',
                },
            },
            Source=source_email
        )
    #delete the processed files but wait first for files to upload to aws et
    time.sleep(20)
    for x in keys:
        response = s3.delete_object(Bucket='video-review-origin', Key=x)









