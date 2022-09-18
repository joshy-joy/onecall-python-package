import hmac
import hashlib
import logging
import time

import pandas as pd
from urllib.parse import urlencode

from base import utils
from base.exchange import Exchange
from base import urls


class Phemex(Exchange):
    """
    Phemex API class


    """
    def __init__(self, key=None, secret=None, debug=False, **kwargs):
        self._path_config = {
            "get_positions": {"method": "GET", "path": "/accounts/accountPositions", "rate_limit": 50},
            "cancel_orders": {"method": "DELETE", "path": "/orders/all", "rate_limit": 50},
            "get_data": {"method": "GET", "path": "/exchange/public/md/v2/kline", "rate_limit": 50},
            "get_orderbook": {"method": "GET", "path": "/md/orderbook", "rate_limit": 50},
            "get_balance": {"method": "GET", "path": "accounts/accountPositions", "rate_limit": 50},
            "market_order": {"method": "POST", "path": "/orders", "rate_limit": 50},
            "limit_order": {"method": "POST", "path": "/orders", "rate_limit": 50},
            "get_closed_orders": {"method": "GET", "path": "/exchange/order/list", "rate_limit": 50},
            "get_open_orders": {"method": "GET", "path": "/orders/activeList", "rate_limit": 50}
        }

        self._LIMIT = 500

        # Constants for Order side
        self.BUY_SIDE = 'BUY'
        self.SELL_SIDE = 'SELL'

        if not debug:
            kwargs["base_url"] = urls.PHEMEX_FUT_BASE_URL
        else:
            kwargs["base_url"] = urls.PHEMEX_FUT_TEST_BASE_URL
        super().__init__(key, secret, **kwargs)
        return

    def get_positions(self, currency="USD"):
        """
        API to get current positions
        :param currency: symbol
        :return: {
                "code": 0,
                    "msg": "",
                    "data": {
                        "positions": [
                            {
                                "accountID": 0,
                                "symbol": "BTCUSD",
                                "currency": "BTC",
                                "side": "None",
                                "positionStatus": "Normal",
                                "crossMargin": false,
                                "leverageEr": 0,
                                "leverage": 0,
                                "initMarginReqEr": 0,
                                "initMarginReq": 0.01,
                                "maintMarginReqEr": 500000,
                                "maintMarginReq": 0.005,
                                "riskLimitEv": 10000000000,
                                "riskLimit": 100,
                                "size": 0,
                                "value": 0,
                                "valueEv": 0,
                                ...
                            }
                        ]
                    }
            }
        """
        params = {
            "currency": currency
        }
        response = self._signed_request(self._path_config.get("get_positions").get("method"),
                                        self._path_config.get("get_positions").get("path"),
                                        params)
        return response.get("data", {}).get("positions")

    def cancel_orders(self, symbol: str):
        """
        API to cancel all orders

        :param symbol: future symbol
        :return: data part of response is subject to change
        """
        params = {
            "symbol": symbol,
            "untriggered": True,
        }
        response = self._signed_request(self._path_config.get("cancel_orders").get("method"),
                                        self._path_config.get("cancel_orders").get("path"),
                                        params)
        return response

    def get_data(self, symbol: str, is_dataframe=False):
        """
        API to get OHLCV data

        :param symbol: future symbol
        :param is_dataframe: whether to return row json/dataframe
        :return: {
            "code": 0,
            "msg": "OK",
            "data": {
                    "total": -1,
                    "rows": [
                        [<timestamp>, <interval>, <last_close>, <open>, <high>, <low>, <close>, <volume>, <turnover>],
                        ]
                }
            }
        """
        params = {
            "symbol": symbol
        }
        response = self._signed_request(self._path_config.get("get_data").get("method"),
                                        self._path_config.get("get_data").get("path"),
                                        params)
        if is_dataframe:
            try:
                columns = ["timestamp", "interval", "last_close", "open", "high", "low", "close", "volume", "turnover"]
                return pd.DataFrame(response["rows"], columns=columns)
            except Exception as e:
                self._logger.error(e)
        return response

    def get_orderbook(self, symbol: str, is_dataframe=False):
        """
        API to get orderbook

        :param symbol: future_symbol
        :param is_dataframe: whether to return row json/dataframe
        :return: {
              "error": null,
              "id": 0,
              "result": {
                "book": {
                  "asks": [[<priceEp>, size>],],
                  "bids": [[<priceEp>, <size>],],
                },
                "depth": 30,
                "sequence": <sequence>,
                "timestamp": <timestamp>,
                "symbol": "<symbol>",
                "type": "snapshot"
              }
            }
        """
        params = {
            "symbol": symbol
        }
        response = self._signed_request(self._path_config.get("get_orderbook").get("method"),
                                        self._path_config.get("get_orderbook").get("path"),
                                        params)
        if is_dataframe:
            try:
                columns = ['price', 'QTY']
                df = pd.DataFrame(response["result"]["book"]["bids"], columns=columns)
                orderbook = df.append(pd.DataFrame(response["result"]["book"]["asks"], columns=columns),
                                      ignore_index=True)
                return orderbook
            except Exception as e:
                logging.error(e)
        return response

    def get_balance(self, currency="USD"):
        """
        API to get account balance

        :param currency: currency. USD,BTC
        :return: {
            "code": 0,
                "msg": "",
                "data": {
                    "account": {
                        "accountId": 0,
                        "currency": "BTC",
                        "accountBalanceEv": 0,
                        "totalUsedBalanceEv": 0
                    },
                }
            }
        """
        params = {
            "currency": currency
        }
        response = self._signed_request(self._path_config.get("get_balance").get("method"),
                                        self._path_config.get("get_balance").get("path"),
                                        params)
        return response.get("data", {}).get("account")

    def market_order(self, client_order_id: str, symbol: str, side: str, order_qty: float, **kwargs):
        """
        API to place market order

        :param client_order_id: client order id
        :param symbol: coin symbol
        :param side: BUY/SELL
        :param order_qty: order quantity
        :keyword timeInForce: Time in force. default to GoodTillCancel
        :keyword reduceOnly: whether reduce position side only
        :return: {
                "code": 0,
                    "msg": "",
                    "data": {
                        "bizError": 0,
                        "orderID": "ab90a08c-b728-4b6b-97c4-36fa497335bf",
                        "clOrdID": "137e1928-5d25-fecd-dbd1-705ded659a4f",
                        "symbol": "BTCUSD",
                        "side": "Sell",
                        "actionTimeNs": 1580547265848034600,
                        "transactTimeNs": 0,
                        "orderType": null,
                        "priceEp": 98970000,
                        "price": 9897,
                        "orderQty": 1,
                        "displayQty": 1,
                        "timeInForce": null,
                        "reduceOnly": false,
                        "stopPxEp": 0,
                        "closedPnlEv": 0,
                        "closedPnl": 0,
                        "closedSize": 0,
                        "cumQty": 0,
                        "cumValueEv": 0,
                        "cumValue": 0,
                        "leavesQty": 1,
                        "leavesValueEv": 10104,
                        "leavesValue": 0.00010104,
                        "stopPx": 0,
                        "stopDirection": "UNSPECIFIED",
                        "ordStatus": "Created"
                    }
            }
        """
        payload = {
            "clOrdID": client_order_id,
            "symbol": symbol,
            "side": side,
            "ordType": "Market",
            "orderQty": order_qty,
            **kwargs
        }
        response = self._signed_request(self._path_config.get("market_order").get("method"),
                                        self._path_config.get("market_order").get("path"),
                                        data=payload)
        return response

    def limit_order(self, client_order_id: str, symbol: str, side: str, order_qty: str, price: float, **kwargs):
        """
        API to place limit order

        :param client_order_id: client order id
        :param symbol: currency symbol
        :param side: BUY/SELL
        :param order_qty: order quantity
        :param price: order price
        :keyword timeInForce: Time in force. default to GoodTillCancel
        :keyword reduceOnly: whether reduce position side only
        :return: {
                "code": 0,
                    "msg": "",
                    "data": {
                        "bizError": 0,
                        "orderID": "ab90a08c-b728-4b6b-97c4-36fa497335bf",
                        "clOrdID": "137e1928-5d25-fecd-dbd1-705ded659a4f",
                        "symbol": "BTCUSD",
                        "side": "Sell",
                        "actionTimeNs": 1580547265848034600,
                        "transactTimeNs": 0,
                        "orderType": null,
                        "priceEp": 98970000,
                        "price": 9897,
                        "orderQty": 1,
                        "displayQty": 1,
                        "timeInForce": null,
                        "reduceOnly": false,
                        "stopPxEp": 0,
                        "closedPnlEv": 0,
                        "closedPnl": 0,
                        "closedSize": 0,
                        "cumQty": 0,
                        "cumValueEv": 0,
                        "cumValue": 0,
                        "leavesQty": 1,
                        "leavesValueEv": 10104,
                        "leavesValue": 0.00010104,
                        "stopPx": 0,
                        "stopDirection": "UNSPECIFIED",
                        "ordStatus": "Created"
                    }
            }
        """
        payload = {
            "clOrdID": client_order_id,
            "symbol": symbol,
            "side": side,
            "ordType": "Limit",
            "orderQty": order_qty,
            "priceEp": price,
            **kwargs
        }
        response = self._signed_request(self._path_config.get("limit_order").get("method"),
                                        self._path_config.get("limit_order").get("path"),
                                        data=payload)
        return response

    def get_closed_orders(self, symbol):
        """
        API to get closed order

        :param symbol: currency symbol
        :return: {
                "code": 0,
                    "msg": "OK",
                    "data": {
                        "total": 39,
                        "rows": [
                        {
                            "orderID": "7d5a39d6-ff14-4428-b9e1-1fcf1800d6ac",
                            "clOrdID": "e422be37-074c-403d-aac8-ad94827f60c1",
                            "symbol": "BTCUSD",
                            "side": "Sell",
                            "orderType": "Limit",
                            "actionTimeNs": 1577523473419470300,
                            "priceEp": 75720000,
                            "price": null,
                            "orderQty": 12,
                            "displayQty": 0,
                            "timeInForce": "GoodTillCancel",
                            "reduceOnly": false,
                            "takeProfitEp": 0,
                            "takeProfit": null,
                            "stopLossEp": 0,
                            ...
                            "ordStatus": "Filled",
                        }
                    ]
                }
            }
        """
        params = {
            "symbol": symbol,
            "ordStatus": "Filled"
        }
        response = self._signed_request(self._path_config.get("get_closed_orders").get("method"),
                                        self._path_config.get("get_closed_orders").get("path"),
                                        params)
        return response

    def get_open_orders(self, symbol):
        """
        API to get all open orders by symbol

        :param symbol: currency symbol
        :return: {
                "code": 0,
                    "msg": "",
                    "data": {
                        "rows": [
                        {
                            "bizError": 0,
                            "orderID": "9cb95282-7840-42d6-9768-ab8901385a67",
                            "clOrdID": "7eaa9987-928c-652e-cc6a-82fc35641706",
                            "symbol": "BTCUSD",
                            "side": "Buy",
                            "actionTimeNs": 1580533011677666800,
                            "transactTimeNs": 1580533011677666800,
                            "orderType": null,
                            "priceEp": 84000000,
                            "price": 8400,
                            "orderQty": 1,
                            "displayQty": 1,
                            "timeInForce": null,
                            "reduceOnly": false,
                            "stopPxEp": 0,
                            "closedPnlEv": 0,
                            "closedPnl": 0,
                            "closedSize": 0,
                            "cumQty": 0,
                            "cumValueEv": 0,
                            "cumValue": 0,
                            "leavesQty": 0,
                            "leavesValueEv": 0,
                            "leavesValue": 0,
                            "stopPx": 0,
                            "stopDirection": "Falling",
                            "ordStatus": "Untriggered"
                        }
                    ]
                }
            }
        """
        params = {
            "symbol": symbol
        }
        response = self._signed_request(self._path_config.get("get_open_orders").get("method"),
                                        self._path_config.get("get_open_orders").get("path"),
                                        params)
        return response

    def _signed_request(self, method, path, params=None, data=None):
        expiry = utils.get_current_timestamp() + 1
        header = self._get_request_credentials(path, expiry, params=params, payload=data)
        response = super().send_request(self, method, path, header, urlencode(params), data)
        return response

    def _get_sign(self, data):
        m = hmac.new(super().secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256)
        return m.hexdigest()

    def _get_request_credentials(self, path, expiry, **kwargs):
        signature = ""
        if kwargs.get("params"):
            signature = self._get_sign(path + urlencode(kwargs.get("params")) + str(expiry))
        elif kwargs.get("payload"):
            signature = self._get_sign(path + str(expiry) + str(kwargs.get("payload")))
        header = {
            "x-phemex-access-token": self.key,
            "x-phemex-request-signature": signature,
            "x-phemex-request-expiry": expiry,
        }
        return header
