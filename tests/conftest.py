import os

# boto3 clients are created at import time in the Lambda handlers, so a region
# and dummy credentials must exist before any test module is collected.
# (GitHub Actions sets AWS_REGION, but boto3 reads AWS_DEFAULT_REGION.)
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
