#!/usr/bin/env python3
import logging
import sys
import redis
import requests
import yaml
from datetime import datetime, timedelta
from hashlib import md5
from os import path
from pytz import timezone

# Constant API-related values
AV_API = 'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY'
AV_TIME_SERIES_KEY = 'Time Series (Daily)'
AV_OPEN_KEY = '1. open'
AV_CLOSE_KEY = '4. close'
COINDESK_CURRENT_API = 'https://api.coindesk.com/v1/bpi/currentprice.json'
COINDESK_HISTORICAL_API = 'https://api.coindesk.com/v1/bpi/historical/close.json'

VERSION = '0.2.3'
config = {}

# Initialize logger
stdout_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    format='%(levelname)s[%(asctime)s] %(message)s',
    handlers=[stdout_handler]
)
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def main(event, context):
    """Fetch percent change for each symbol and send an alert email if it
    exceeds the alert threshold.

    Args: https://docs.aws.amazon.com/lambda/latest/dg/python-programming-model-handler-types.html
        event: Event data passed by AWS Lambda
        context: Runtime information passed by AWS Lambda
    """
    # Load config
    with open(path.join(sys.path[0], 'config.yaml'), 'r') as config_file:
        global config
        config = yaml.load(config_file)
        logger.debug(config)

    # Initialize cache
    cache = redis.Redis(
        host=config['redis']['host'],
        port=config['redis']['port'],
        password=config['redis']['password'])
    try:
        cache.ping()
    except redis.exceptions.ConnectionError as e:
        logger.fatal('Error connecting to Redis: %s', e)
        sys.exit(1)

    # Fetch percent change for each symbol
    for symbol in config['alert']['symbols']:
        try:
            percent_change, time = get_symbol_percent_change(symbol)
        except Exception as e:
            logger.error('Error looking up %s: %s', symbol, e)
            continue
        logger.info('%s - %s', symbol, time)
        logger.info('Percent change: %s%%', percent_change)
        # Alert if threshold exceeded and alert not already sent
        if abs(percent_change) >= config['alert']['threshold']:
            alert_timedelta = timedelta(hours=config['alert']['timedelta'])
            cache_key = md5(symbol.encode() + config['mailgun']['to'].encode()).hexdigest()
            alerted = cache.get(cache_key)
            if alerted is None:
                try:
                    cache.set(cache_key, 1, alert_timedelta)
                    send_alert_email(symbol, percent_change, time)
                    logger.info('Alert sent to %s', config['mailgun']['to'])
                except Exception as e:
                    logger.fatal('Error sending alert email: %s', e)
                    sys.exit(1)
            else:
                logger.warning('No alert sent: alerted within past %s', alert_timedelta)


def get_symbol_percent_change(symbol):
    """Call correct percent change function based on symbol's market.

    Args:
        symbol (str): Percent change for BTC since yesterday
    """
    if symbol == 'BTC':
        return get_bitcoin_percent_change()
    return get_stock_percent_change(symbol)


def get_bitcoin_percent_change():
    """Fetch today's percent change for BTC.

    Uses Coindesk's API for current and previous day's price data.

    Returns:
        percent_change (float): Percent change for BTC since yesterday
        time (str): Time of most recent data point
    """
    historical_response = requests.get(COINDESK_HISTORICAL_API)
    historical_json = historical_response.json()
    current_price_response = requests.get(COINDESK_CURRENT_API)
    current_price_json = current_price_response.json()
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    yesterday_price = historical_json['bpi'][yesterday]
    current_price = current_price_json['bpi']['USD']['rate_float']
    current_price_updated = current_price_json['time']['updatedISO']
    logger.debug('%s BTC @ %s', yesterday_price, yesterday)
    logger.debug('%s BTC @ %s', current_price, current_price_updated)
    percent_change = calculate_percent_change(yesterday_price, current_price)
    return percent_change, current_price_updated


def get_stock_percent_change(symbol):
    """Fetch today's percent change for a stock symbol.

    Uses AlphaVantage's API for daily stock data.

    Args:
        symbol (str): Stock symbol to look up

    Returns:
        percent_change (float): Percent change for symbol since market open
        time (str): Time of most recent data point
    """
    response = requests.get(AV_API + '&symbol={}&apikey={}'.
                            format(symbol, config['alphavantage_api_key']))
    response_json = response.json()
    now_est = datetime.now(timezone('America/New_York'))
    today = now_est.strftime('%Y-%m-%d')
    # Keys may look like '2017-08-11 13:26:00' or '2017-08-10',
    # so loop through all keys to find today's data
    for key in response_json[AV_TIME_SERIES_KEY].keys():
        if today in key:
            today_data = response_json[AV_TIME_SERIES_KEY][key]
            logger.debug('%s %s', key, today_data)
            delta = 1
            # Step backwards to find previous trading day
            while True:
                previous_day = now_est - timedelta(days=delta)
                last_trading_day = previous_day.strftime('%Y-%m-%d')
                try:
                    last_trading_day_data = response_json[AV_TIME_SERIES_KEY][last_trading_day]
                    logger.debug('%s %s', last_trading_day, last_trading_day_data)
                    percent_change = calculate_percent_change(float(last_trading_day_data[AV_CLOSE_KEY]),
                                                              float(today_data[AV_CLOSE_KEY]))
                    return percent_change, key + ' EST'
                except KeyError:
                    delta += 1

        # Today not found in API response
        raise Exception('No data found for {}'.format(today))


def send_alert_email(symbol, percent_change, time):
    """Send email to configured recipient. Uses Mailgun to send the alert.

    Args:
        symbol (str): Symbol which passed alert threshold
        percent_change (float): Current percent change
        time (str): Time at which alert was generated
    """
    response = requests.post(
        config['mailgun']['api'],
        auth=('api', config['mailgun']['api_key']),
        data={'from': config['mailgun']['from'],
              'to': config['mailgun']['to'],
              'subject': '[flux_watch] {} moved {}%'.format(symbol, round(percent_change, 2)),
              'text': 'Symbol: {}\nMovement: {}% (exact: {}%)\nTimestamp: {}\n\nflux_watch v{}'.
                      format(symbol, round(percent_change, 2), percent_change, time, VERSION)})
    if response.status_code != requests.codes.ok:
        raise Exception('%s: %s', response.status_code, response.text)


def calculate_percent_change(a, b):
    return ((b - a) / a) * 100

if __name__ == '__main__':
    main({}, {})
