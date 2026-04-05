import boto3


ssm = boto3.client("ssm", region_name="ap-south-1")


def get_job_status_ssm(job_id: str) -> str | None:
    """Read job status from SSM Parameter Store. Key: {job_id}_status, complete value: 'd'"""
    param_name = f"{job_id}_status"
    try:
        response = ssm.get_parameter(Name=param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return None
    except Exception as e:
        print(f"SSM get error for {param_name}: {e}")
        return None
