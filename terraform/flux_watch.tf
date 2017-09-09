provider "aws" {
  region = "us-east-1"
}

resource "aws_iam_role" "flux_watch_iam" {
  name = "flux_watch_iam"

  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy" "flux_watch_policy" {
  name = "flux_watch_policy"
  role = "${aws_iam_role.flux_watch_iam.id}"

  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:Describe*",
        "cloudwatch:Get*",
        "cloudwatch:List*"
      ],
      "Resource": "*"
    }
  ]
}
POLICY
}

resource "aws_lambda_function" "flux_watch_lambda" {
  function_name    = "flux_watch"
  filename         = "../flux_watch.zip"
  role             = "${aws_iam_role.flux_watch_iam.arn}"
  handler          = "flux_watch.main"
  source_code_hash = "${base64sha256(file("../flux_watch.zip"))}"
  runtime          = "python3.6"
  timeout          = "15"
}

# Run every 5 mins, barring 2am-7am PDT
# See also: https://github.com/hashicorp/terraform/issues/4393
resource "aws_cloudwatch_event_rule" "five_mins_waking_hours" {
  name                = "five_mins_waking_hours"
  description         = "Fires every five minutes, minus sleep time"
  schedule_expression = "cron(0/5 0-9,14-23 ? * * *)"
}

resource "aws_cloudwatch_event_target" "run_flux_watch_lambda" {
  rule      = "${aws_cloudwatch_event_rule.five_mins_waking_hours.name}"
  target_id = "flux_watch_lambda"
  arn       = "${aws_lambda_function.flux_watch_lambda.arn}"
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_flux_watch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.flux_watch_lambda.function_name}"
  principal     = "events.amazonaws.com"
  source_arn    = "${aws_cloudwatch_event_rule.five_mins_waking_hours.arn}"
}
