import boto3

s3 = boto3.client('s3')

#values below are set in origin cfn template
origin_bucket = "non-approved-files"
destination_bucket = "approved-bucket"

def lambda_handler(event, context):
    source = event['approval']
    key=[]
    #resolve the pn and timecode from approval parameter
    key = source.rsplit('-',1)
    pn = key[0]
    timecode = key[1]
    #reconstruct object keys for videos and thumbnails
    source_video_object = "videos/"+pn+"-"+timecode+".mp4"
    source_thumbnail_object = "thumbnails/00001-thumbnail-"+pn+"-"+timecode+".jpg"
    #move the video and thumbnail to the approved bucket
    response = s3.copy_object(
        Bucket="approved-bucket",
        CopySource={'Bucket' : 'non-approved-files', 'Key' : source_video_object},
        Key=source_video_object
    )
    response = s3.copy_object(
        Bucket="approved-bucket",
        CopySource={'Bucket' : 'non-approved-files', 'Key' : source_thumbnail_object},
        Key=source_thumbnail_object
    )
    return("approved!")
    #you could delete the objects here, but why bother? the lifecycle policy will collect the garbage

