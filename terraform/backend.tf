# --------------------------------------------------------------------------
# Remote state backend.
#
# Bootstrap manually BEFORE running `terraform init` (do this once, by hand -
# this is intentional: you don't want your state bucket's own creation to
# depend on Terraform state that doesn't exist yet). This is a legitimate
# "chicken-and-egg" problem worth explaining in an interview.
#
#   aws s3api create-bucket --bucket pipelinewatch-tfstate-pipo7007 \
#       --region ap-south-1
#   aws s3api put-bucket-versioning --bucket pipelinewatch-tfstate-pipo7007 \
#       --versioning-configuration Status=Enabled
#   aws dynamodb create-table --table-name pipelinewatch-tf-lock-table \
#       --attribute-definitions AttributeName=LockID,AttributeType=S \
#       --key-schema AttributeName=LockID,KeyType=HASH \
#       --billing-mode PAY_PER_REQUEST
#
# Then fill in the bucket name below and run `terraform init`.
# --------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "s3" {
    bucket         = "pipelinewatch-tfstate-pipo7007"
    key            = "dev/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "pipelinewatch-tf-lock-table"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
