import uuid
import jwt

from datetime import timedelta
import datetime
from django.utils import timezone
import time
import requests
import json
from binance.client import Client
import ccxt

from config.global_variable import selected_coin_kind, market_withdraw_fee_info
from bit_finance.models import BitFinanceExchange
from config.global_variable import bits_name_list
from config.settings.base import SECRETS_FULL
from up_bits.models import UpBitMarket, UpBitExchange

date_time_now = timezone.now() + timezone.timedelta(hours=9)
datetime_now = datetime.datetime(date_time_now.year,
                                 date_time_now.month,
                                 date_time_now.day,
                                 date_time_now.hour,
                                 date_time_now.minute)

date_time_now = timezone.now() + timezone.timedelta(hours=9) - timezone.timedelta(minutes=1)
datetime_now_before_one_minute = datetime.datetime(date_time_now.year,
                                                   date_time_now.month,
                                                   date_time_now.day,
                                                   date_time_now.hour,
                                                   date_time_now.minute)


def search_binance():
    binance = ccxt.binance()
    markets = binance.fetch_tickers()
    objects = list()

    bit_coin_value = markets['BTC/BKRW']['close']
    BINANCE_KEY = SECRETS_FULL['BINANCE_KEY']
    binance_access_key = BINANCE_KEY['access_key']
    binance_secret_key = BINANCE_KEY['secret_key']
    client = Client(binance_access_key, binance_secret_key)
    assetDetail_data = client.get_asset_details()
    assetDetail = assetDetail_data['assetDetail']
    time.sleep(0.5)
    for symbol in markets:
        time_string = markets[symbol]['datetime'][:16]
        datetime_data = datetime.datetime.strptime(time_string, '%Y-%m-%dT%H:%M') + timedelta(hours=9)
        datetime_data = datetime.datetime(datetime_data.year, datetime_data.month, datetime_data.day,
                                          datetime_data.hour, datetime_data.minute)
        # BTC ?????????
        market_name = symbol.split('/')[1]
        # coin ??????
        coin_kind_name = symbol.split('/')[0]
        # kind['market'] != 'KRW-BTC' and kind['market'].split('-')[0] != 'BTC':

        if 'BTC/BKRW' != symbol and 'BTC' != market_name:
            continue

        try:
            asset_withdraw_enable_dict = assetDetail[coin_kind_name]
            depositStatus = asset_withdraw_enable_dict['depositStatus']
            # withdrawFee = asset_withdraw_enable_dict['withdrawFee']
            withdrawStatus = asset_withdraw_enable_dict['withdrawStatus']
        except Exception as e:
            print('withdraw Exception', e)
            depositStatus = False
            # withdrawFee = 0
            withdrawStatus = False

        if datetime_data != datetime_now:
            datetime_data = datetime_now
        try:
            obj, _ = UpBitMarket.objects.get_or_create(coin=coin_kind_name)
        except Exception as e:
            print('market model create Exception', e)
            # obj, _ = UpBitMarket.objects.get_or_create(
            #     coin=coin_kind_name,
            #     up_bit_withdraw_fee=0.0,
            #     up_bit_deposit_fee=0.0,
            #     up_bit_minimum_with_draw_amount=0.0,
            #     binance_withdraw_fee=0.0,
            #     binance_deposit_fee=0.0,
            #     binance_minimum_with_draw_amount=0.0
            # )

        up_bit_obj = BitFinanceExchange(
            market=obj,
            english_name=markets[symbol]['symbol'],
            candle_date_time_kst=datetime_data,
            bit_coin_value=bit_coin_value,
            deposit_status=depositStatus,
            withdraw_status=withdrawStatus,
            open_price=markets[symbol]['open'],
            low_price=markets[symbol]['low'],
            high_price=markets[symbol]['high'],
            close_price=markets[symbol]['close'],
            volume=markets[symbol]['info']['quoteVolume'],
        )
        objects.append(up_bit_obj)
    BitFinanceExchange.objects.bulk_create(objects)


def single_compare_time_now_with_response_datetime(current_data, time_now_list):
    c_data = current_data[0]
    time_data = datetime.datetime.strptime(c_data['candle_date_time_kst'].replace('T', ' '), '%Y-%m-%d %H:%M:00')
    response_datetime = datetime.datetime(time_data.year, time_data.month, time_data.day, time_data.hour,
                                          time_data.minute)
    if response_datetime != time_now_list:
        c_data['candle_date_time_kst'] = time_now_list
    return c_data


def with_draw_api_request_up_bit():
    UP_BIT_KEY = SECRETS_FULL['UP_BIT_KEY']
    access_key = UP_BIT_KEY['access_key']
    secret_key = UP_BIT_KEY['secret_key']

    server_url = 'https://api.upbit.com'
    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
    }
    jwt_token = jwt.encode(payload, secret_key)
    authorize_token = 'Bearer {}'.format(jwt_token)
    headers = {"Authorization": authorize_token}
    res = requests.get(server_url + "/v1/status/wallet", headers=headers)
    print(res.status_code)
    try:
        print('withdraw api ', res.json()[:2])

    except Exception as e:
        print('wallet api  ?????? ??????', e)
        print('text ?????? ', res.text[:100])
    print(datetime_now)
    if res.status_code == 401 or res.status_code == 404 or res.status_code == 429:
        return None
    status_withdraw = res.json()
    coin_kind_for_find_dict = dict()
    for i in status_withdraw:
        coin_currency_kind = i['currency']
        coin_kind_for_find_dict[coin_currency_kind] = i

    return coin_kind_for_find_dict


def bulk_up_bit_current_create(current_search_list):
    # ???????????? ?????? api ??????
    url = "https://api.upbit.com/v1/candles/minutes/1"
    querystring = {"market": "KRW-BTC", "count": "1"}
    response = requests.request("GET", url, params=querystring)
    bit_coin_value = response.json()[0]['trade_price']

    objects = list()
    for data in current_search_list:
        coin_for_fee_value = data['market'].split('-')[1]
        if data['with_enable'] is not None:
            wallet_state = data['with_enable']
            if wallet_state == 'working':
                withdraw_status = True
                deposit_status = True
            elif wallet_state == 'withdraw_only':
                withdraw_status = True
                deposit_status = False
            elif wallet_state == 'deposit_only':
                withdraw_status = False
                deposit_status = True
            else:
                withdraw_status = False
                deposit_status = False
        else:
            withdraw_status = False
            deposit_status = False
        # try:
        #     fee_data_dict = market_withdraw_fee_info[data['market'].split('-')[1]]
            # obj, _ = UpBitMarket.objects.get_or_create(
            #     coin=data['market'].split('-')[1]
            #     up_bit_withdraw_fee=fee_data_dict['????????????????????????']
            #     up_bit_deposit_fee=0.0
            #     up_bit_minimum_with_draw_amount=fee_data_dict['???????????????????????????']
            #     binance_withdraw_fee=fee_data_dict['???????????????????????????']
            #     binance_deposit_fee=0.0
            #     binance_minimum_with_draw_amount=fee_data_dict['??????????????????????????????']
            #
            # )
        #     market_get_or_create = True
        # except Exception as e:
        #     market_get_or_create = False
        #     print(e)
        # if not market_get_or_create:
        try:
            print(data['market'])
            obj, _ = UpBitMarket.objects.get_or_create(
                coin=data['market'].split('-')[1],
            )
        except Exception as e:
            print('???????????? ??????', e)

        try:
            fee_data_dict = market_withdraw_fee_info[coin_for_fee_value]
            obj.up_bit_deposit_fee = 0.0
            obj.up_bit_withdraw_fee = fee_data_dict['????????????????????????']
            obj.up_bit_minimum_with_draw_amount = fee_data_dict['???????????????????????????']
            obj.binance_deposit_fee = 0.0
            obj.binance_withdraw_fee = fee_data_dict['???????????????????????????']
            obj.binance_minimum_with_draw_amount = fee_data_dict['??????????????????????????????']
            obj.save()
            print('???????????? ?????? ', obj)
        except Exception as e:
            # pass
            print('???????????? ??????', e)
        # print('obj', obj)
        objects.append(
            UpBitExchange(
                market=obj,
                full_name=data['full_name'],
                korean_name=data['korean_name'],
                english_name=data['english_name'],
                bit_coin_value=bit_coin_value,
                withdraw_status=withdraw_status,
                deposit_status=deposit_status,
                candle_date_time_kst=data['candle_date_time_kst'],
                open_price=data['opening_price'],
                low_price=data['low_price'],
                high_price=data['high_price'],
                close_price=data['trade_price'],
                volume=data['candle_acc_trade_volume'],
            )
        )
    return objects


def search_up_bit_first():

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
    }
    url = "https://api.upbit.com/v1/candles/minutes/1"
    # ????????? ???????????? api ?????? ????????? ?????????
    coin_kind_for_find_dict = with_draw_api_request_up_bit()

    current_search_list = list()
    # bits_name_list ??????????????? ???????????? ?????? ????????? api ?????? ????????? ?????? ???????????? ???????????? ??????
    for kind in bits_name_list[:55]:
        coin_full_name = kind['market']
        coin_exchange_kind_split = coin_full_name.split('-')
        # ?????? ?????????
        coin_exchange = coin_exchange_kind_split[0]
        # ?????? ??????
        coin_kind = coin_exchange_kind_split[1]
        # KRW-BTC ??????????????? ????????? ???????????? ???????????? ?????? ??????
        # ?????? ???????????? False ?????? ?????????
        if coin_full_name != 'KRW-BTC' and coin_exchange != 'BTC':
            continue
        # ????????? ?????? api ??????
        querystring = {"market": f"{coin_full_name}", "count": "1"}
        response = requests.request("GET", url, headers=headers, params=querystring)
        try:
            current_data = response.json()
        except Exception as e:
            print('????????? ????????? ?????? ?????? ?????? api ????????? ????????? ?????? ?????? ?????? json type error', e, response.status_code)
            try:
                current_data = json.loads(response.text)
            except Exception as e:
                print('????????? ????????? ?????? ?????? ?????? api ????????? ????????? ?????? ?????? ?????? text error', e, response.status_code)
                continue
        five_ea_data_list = single_compare_time_now_with_response_datetime(current_data, datetime_now)
        five_ea_data_list['english_name'] = kind['english_name']
        five_ea_data_list['korean_name'] = kind['korean_name']
        five_ea_data_list['full_name'] = coin_full_name
        if coin_kind_for_find_dict is not None:
            # ????????? ???????????? ????????? ?????????????????? assign
            with_draw_enable = coin_kind_for_find_dict[coin_kind]
            five_ea_data_list['with_enable'] = with_draw_enable['wallet_state']
        else:
            five_ea_data_list['with_enable'] = None
        current_search_list.append(five_ea_data_list)
        time.sleep(1)
    bits_objects = bulk_up_bit_current_create(current_search_list)
    UpBitExchange.objects.bulk_create(bits_objects)


def search_up_bit_second():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    url = "https://api.upbit.com/v1/candles/minutes/1"
    time.sleep(1)
    coin_kind_for_find_dict = with_draw_api_request_up_bit()

    current_search_list = list()
    for kind in bits_name_list[55:110]:
        coin_full_name = kind['market']
        coin_exchange_kind_split = coin_full_name.split('-')
        coin_exchange = coin_exchange_kind_split[0]
        coin_kind = coin_exchange_kind_split[1]

        if coin_full_name != 'KRW-BTC' and coin_exchange != 'BTC':
            continue
        querystring = {"market": f"{coin_full_name}", "count": "1"}
        response = requests.request("GET", url, headers=headers, params=querystring)
        try:
            current_data = response.json()
        except Exception as e:
            print('????????? ????????? ?????? ?????? ?????? api ????????? ????????? ?????? ?????? ?????? json type error', e, response.status_code)
            try:
                current_data = json.loads(response.text)
            except Exception as e:
                print('????????? ????????? ?????? ?????? ?????? api ????????? ????????? ?????? ?????? ?????? text error', e, response.status_code)
                continue
        five_ea_data_list = single_compare_time_now_with_response_datetime(current_data, datetime_now)
        five_ea_data_list['english_name'] = kind['english_name']
        five_ea_data_list['korean_name'] = kind['korean_name']
        five_ea_data_list['full_name'] = coin_full_name
        if coin_kind_for_find_dict is not None:
            with_draw_enable = coin_kind_for_find_dict[coin_kind]
            five_ea_data_list['with_enable'] = with_draw_enable['wallet_state']
        else:
            five_ea_data_list['with_enable'] = None
        current_search_list.append(five_ea_data_list)
        time.sleep(1)
    bits_objects = bulk_up_bit_current_create(current_search_list)
    UpBitExchange.objects.bulk_create(bits_objects)


def search_up_bit_third():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    url = "https://api.upbit.com/v1/candles/minutes/1"
    time.sleep(2)
    coin_kind_for_find_dict = with_draw_api_request_up_bit()

    current_search_list = list()
    for kind in bits_name_list[110:]:
        coin_full_name = kind['market']
        coin_exchange_kind_split = coin_full_name.split('-')
        coin_exchange = coin_exchange_kind_split[0]
        coin_kind = coin_exchange_kind_split[1]
        if coin_full_name != 'KRW-BTC' and coin_exchange != 'BTC':
            continue
        querystring = {"market": f"{coin_full_name}", "count": "1"}
        response = requests.request("GET", url, headers=headers, params=querystring)
        try:
            current_data = response.json()
        except Exception as e:
            print('????????? ????????? ?????? ?????? ?????? api ????????? ????????? ?????? ?????? ?????? json type error', e, response.status_code)
            try:
                current_data = json.loads(response.text)
            except Exception as e:
                print('????????? ????????? ?????? ?????? ?????? api ????????? ????????? ?????? ?????? ?????? text error', e, response.status_code)
                continue
        five_ea_data_list = single_compare_time_now_with_response_datetime(current_data, datetime_now)
        five_ea_data_list['english_name'] = kind['english_name']
        five_ea_data_list['korean_name'] = kind['korean_name']
        five_ea_data_list['full_name'] = coin_full_name
        if coin_kind_for_find_dict is not None:
            with_draw_enable = coin_kind_for_find_dict[coin_kind]
            five_ea_data_list['with_enable'] = with_draw_enable['wallet_state']
        else:
            five_ea_data_list['with_enable'] = None
        current_search_list.append(five_ea_data_list)
        time.sleep(1)
    bits_objects = bulk_up_bit_current_create(current_search_list)
    UpBitExchange.objects.bulk_create(bits_objects)


def save_execute_table():
    for coin_name in selected_coin_kind.values():

        market_obj = UpBitMarket.objects.get(coin=coin_name)
        # ??????????????? = ???????????????????????? ?????? ??????????????? ?????? ?????????(??????)
        up_bit_withdraw_fee = market_obj.up_bit_withdraw_fee
        up_bit_minimum_with_draw_amount = market_obj.up_bit_minimum_with_draw_amount
        up_bit_deposit_fee = market_obj.up_bit_deposit_fee
        # ???????????? ????????? ?????? & 1?????? ????????? ????????????
        binance_withdraw_fee = market_obj.binance_withdraw_fee
        binance_minimum_with_draw_amount = market_obj.binance_withdraw_fee
        binance_deposit_fee = market_obj.binance_deposit_fee

        # ????????? ????????? ?????? & 1?????? ????????? ????????????
        up_obj = market_obj.upbitexchange_set.filter(candle_date_time_kst=datetime_now_before_one_minute)
        binance_obj = market_obj.bitfinanceexchange_set.filter(candle_date_time_kst=datetime_now_before_one_minute)
        up_percentage = 0.9975
        binance_percentage = 0.999
        if up_obj.exists() and binance_obj.exists():
            up_obj = up_obj.first()
            up_bit_volume = up_obj.volume
            market_obj = up_obj.market
            up_close_price = up_obj.close_price
            # ?????? ???????????? = ???????????????????????? ?????? ????????????
            #         up_percentage = 0.9975
            # ????????? ???????????? ??????
            up_bit_coin_value = up_obj.bit_coin_value
            # ?????????????????? ?????? BTC ?????????
            up_init_have_btc_amount = 300000 / up_bit_coin_value
            # ??????????????? ALT ????????? = ?????? BTC ????????? * (1-??????????????????) / ?????????
            up_alt_purchase_price = up_init_have_btc_amount * up_percentage / up_close_price
            # ALT ????????? = ALT ????????? - ???????????????
            up_alt_deposit_amount = up_alt_purchase_price - up_bit_withdraw_fee
            # print('????????? ', up_alt_deposit_amount)
            #         ???????????????
            binance_obj = binance_obj.first()
            binance_volume = binance_obj.volume
            binance_close_price = binance_obj.close_price
            # ?????? BTC ????????? = ALT ????????? * (1 - ??????????????????) * ?????????
            # print('??????', binance_close_price)
            up_final_have_btc_coin = up_alt_deposit_amount * binance_percentage * binance_close_price
            up_expected_revenue_rate = ((up_final_have_btc_coin / up_init_have_btc_amount) - 1) * 100
            # print('????????? ???????????????', up_expected_revenue_rate)

            up_obj.expected_revenue_rate = up_expected_revenue_rate
            up_obj.up_discrepancy_rate = binance_close_price / up_close_price
            # ???????????? = (??????????????? ????????? * ??????????????? ?????????) + (??????????????? ????????? * ??????????????? ?????????)
            up_obj.transaction_price = up_bit_volume * up_close_price

            up_obj.save()

            # ?????????????????? ?????? ??????
            binance_bit_coin_value = binance_obj.bit_coin_value
            #         # ?????????????????? ?????? BTC ?????????
            binance_init_have_btc_amount = 300000 / binance_bit_coin_value
            # print('??????', binance_close_price)
            # print('??????', binance_init_have_btc_amount)
            binance_alt_purchase_price = binance_init_have_btc_amount * binance_percentage / binance_close_price
            binance_alt_deposit_amount = binance_alt_purchase_price - binance_withdraw_fee
            # print('??????', up_close_price)
            # print('percentage', up_percentage)
            # print('?????? ?????? ???', binance_alt_deposit_amount)
            binance_final_have_btc_coin = binance_alt_deposit_amount * up_percentage * up_close_price
            binance_expected_revenue_rate = ((binance_final_have_btc_coin / binance_init_have_btc_amount) - 1) * 100
            binance_obj.expected_revenue_rate = binance_expected_revenue_rate
            binance_obj.binance_discrepancy_rate = up_close_price / binance_close_price
            binance_obj.transaction_price = binance_volume * binance_close_price
            binance_obj.save()

