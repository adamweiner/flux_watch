# flux_watch
Track daily percent change for stock symbols and/or Bitcoin using AWS Lambda. If the configurable daily percent change threshold is crossed, an email alert will be dispatched. To avoid spamming on a day with lots of movement, one can configure the interval on which they wish to receive alerts for each symbol - the sample configuration limits alerts to one per symbol per hour.

Stock price data is provided by [AlphaVantage](https://www.alphavantage.co/). Bitcoin price data is powered by [CoinDesk](https://www.coindesk.com/price/).

## Requirements
- python3
- terraform
- redis
- [AlphaVantage API key](https://www.alphavantage.co/support/#api-key)
- [Mailgun account](https://www.mailgun.com/)

## Usage
1. Update `flux_watch/config.sample.yaml` (AlphaVantage API key, Mailgun config, Redis config)
2. Rename `flux_watch/config.sample.yaml` -> `flux_watch/config.yaml`
3. Install requirements:
  ```
  $ make reqs
  pip3 install --upgrade -r flux_watch/requirements.txt -t ./flux_watch/
  ...
  ```
4. Run locally:
  ```
  $ make run
  python3 flux_watch/flux_watch.py
  INFO[2017-08-15 11:52:13,477] TQQQ - 2017-08-15 11:52:00 EST
  INFO[2017-08-15 11:52:13,477] Percent change: -0.008999280057599996%
  INFO[2017-08-15 11:52:14,650] BTC - 2017-08-15T15:52:00+00:00
  INFO[2017-08-15 11:52:14,650] Percent change: -7.138910982493986%
  WARNING[2017-08-15 11:52:14,675] No alert sent: alerted within past 1:00:00
  ```

## Deployment
Terraform is used to manage deployment to AWS. As provided, `terraform/flux_watch.tf` will run `flux_watch` every five minutes (barring some late night hours, PST :zzz:). This project forgoes Elasticache, since companies such as [Redis Labs](https://redislabs.com/pricing/redis-cloud/) provide a free tier that meets the minimal caching requirements that this project has. You may wish to consider Elasticache to run both the Lambda function and cache within a secure VPC, but that is not done here. One of the goals of this project is to minimize cost of deployment. Deployment can be done in one shot using the `make deploy` target, or step-by-step as outlined below.

1. `$ make zip`
2. `$ AWS_ACCESS_KEY_ID=akid AWS_SECRET_ACCESS_KEY=sak make plan`
3. `$ AWS_ACCESS_KEY_ID=akid AWS_SECRET_ACCESS_KEY=sak make apply`
