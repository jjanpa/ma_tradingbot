import datetime
import os
import pandas as pd
import pyupbit
import telegram
import threading
import time
import traceback
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler


class bot_ticker():     # 각 티커의 세부 값을 저장하는 티커변수 Class
    def __init__(self):
        self.ticker = ''
        self.flag_sys = 1
        self.portion = 1
        self.MA1_period = 10
        self.MA2_period = 55
        self.MA_flow_period = 494
        self.pre_MA1 = 0
        self.pre_MA2 = 0
        self.pre_MA_flow = 0
        self.prepre_MA_flow = 0
        self.MA1 = 0
        self.MA2 = 0
        self.MA_flow = 0
        self.status = 'waiting'
        self.price_now = 100.0
        self.price_buy = 0.0
        self.price_sell = 0.0
        self.amount_buy = 0.0
        self.to_work = False


class TradingBot():     # 각 거래소 봇 Class
    def __init__(self):
        print('init')
        ### 변수 설정(공통)
        self.ex_mode = False    # 연습모드 활성화, 실제 매매시 False

        self.id = ''
        self.trading = 'upbit'
        self.KRW = 0
        self.list_ticker = []
        self.num_buying = 0
        self.free_portion = 1
        self.loss_cut = 100
        self.period = '1d'
        self.column_ohlcv = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        self.column_trading = ['timestamp', 'ticker', 'period_MA1', 'period_MA2', 'period_MA_flow', 'side', 'MA1', 'MA2', 'MA_flow', 'price buy', 'amount buy', 'price sell']
        self.walking = ['init', 'buying', 'selling', 'waiting after buying', 'waiting after selling']
        self.volume_buy = 0.0
        self.now_time = datetime.datetime.now()
        self.next_time = datetime.datetime.now()
        self.msg = ''

    def set_value(self, list_ticker):
        try:
            print('set_value')
            tmp = pyupbit.get_ohlcv(list_ticker.ticker, interval="minute60", count=list_ticker.MA_flow_period+5)
            list_ticker.prepre_MA_flow = tmp.tail(list_ticker.MA_flow_period+3)[:-3]['close'].mean()
            list_ticker.pre_MA1 = tmp.tail(list_ticker.MA1_period+2)[:-2]['close'].mean()
            list_ticker.pre_MA2 = tmp.tail(list_ticker.MA2_period+2)[:-2]['close'].mean()
            list_ticker.pre_MA_flow = tmp.tail(list_ticker.MA_flow_period+2)[:-2]['close'].mean()
            list_ticker.MA1 = tmp.tail(list_ticker.MA1_period+1)[:-1]['close'].mean()
            list_ticker.MA2 = tmp.tail(list_ticker.MA2_period+1)[:-1]['close'].mean()
            list_ticker.MA_flow = tmp.tail(list_ticker.MA_flow_period+1)[:-1]['close'].mean()
            print(f'set_value : {list_ticker.ticker}\n{list_ticker.pre_MA1} {list_ticker.pre_MA2} {list_ticker.pre_MA_flow}\n{list_ticker.MA1} {list_ticker.MA2} {list_ticker.MA_flow}')
        except Exception as e:
            print(f'fail set_value : {traceback.print_exc()}')

    def check_trade(self, list_ticker):
        try:
            if len(self.list_trade) > 0:
                is_ticker = self.list_trade['ticker'] == list_ticker.ticker
                is_MA1 = self.list_trade['period_MA1'] == list_ticker.MA1_period
                is_MA2 = self.list_trade['period_MA2'] == list_ticker.MA2_period
                is_MA_flow = self.list_trade['period_MA_flow'] == list_ticker.MA_flow_period
                trade = self.list_trade[is_ticker & is_MA1 & is_MA2 & is_MA_flow]
                if len(trade) > 0:
                    if trade.iloc[-1]['side'] == 'buy':
                        list_ticker.price_buy = trade.iloc[-1]['price buy']
                        list_ticker.amount_buy = trade.iloc[-1]['amount buy']
                        self.free_portion -= list_ticker.portion
                        self.free_portion = round(self.free_portion,1)
                        self.msg = f'already buying : {list_ticker.ticker}\n{self.trading}({self.id})\n'
                        self.msg += f'price buy : {list_ticker.price_buy:,.2f}\n'
                        self.msg += f'amount buy : {list_ticker.amount_buy:,.2f}'
                        print(self.msg)
                        print(list_ticker.amount_buy,type(list_ticker.amount_buy))
                        list_ticker.flag_sys = 2
                    else:
                        list_ticker.flag_sys = 1
                else:
                    list_ticker.flag_sys = 1
            return True
        except Exception as e:
            print(traceback.print_exc())
            self.msg = 'fail check trade'
            return False

    def searching(self, list_ticker):
        try:
            if list_ticker.MA1 > list_ticker.MA2 and list_ticker.pre_MA1 < list_ticker.pre_MA2 and list_ticker.MA_flow > list_ticker.pre_MA_flow:      #기준 시점 도달시
                if self.buy_ticker(list_ticker):
                    self.num_buying += 1
                    print('success buying~')
                    return 2
                else:
                    print(f'fail buying...{list_ticker.ticker}')
                    return 9
            else:
                return 1
        except Exception as e:
            print('searching fail : ',traceback.print_exc())
            self.msg = 'searching fail'
            return 9

    def buy_ticker(self, list_ticker):
        try:
            print(f'buy ticker : {list_ticker.ticker} {self.ex_mode}')

            if not self.free_portion == 0.0:
                if self.ex_mode:
                    print('ex mode')
                    self.msg = 'ex mode'
                    self.volume_buy = self.KRW * (list_ticker.portion / self.free_portion)
                else:
                    print('actual mode')
                    self.msg = 'actual mode'
                    self.volume_buy = self.trade_upbit.get_balance("KRW") * (list_ticker.portion / self.free_portion)
            list_ticker.price_buy = list_ticker.price_now
            print(f'start buy\n{self.trading}({self.id}) {list_ticker.ticker}\namount buy : {self.volume_buy} / price buy : {list_ticker.price_buy}')
            self.msg += f'start buy\n{self.trading}({self.id}) {list_ticker.ticker}\namount buy : {self.volume_buy} / price buy : {list_ticker.price_buy}'
            if self.volume_buy >= self.margin_money:
                if self.ex_mode:
                    # tmp_price = pyupbit.get_orderbook(ticker=ticker__.ticker)['orderbook_units'][0]['ask_price']
                    orderbook = pd.DataFrame(pyupbit.get_orderbook(ticker=list_ticker.ticker))
                    print('orderbook',len(orderbook))
                    accum_amount = 0
                    accum_volume = 0
                    for i in range(0,len(orderbook),1):
                        ask_price = orderbook.iloc[i]['orderbook_units']['ask_price']
                        ask_size = orderbook.iloc[i]['orderbook_units']['ask_size']
                        if accum_volume + ask_price * ask_size < self.volume_buy:
                            accum_volume += ask_price * ask_size
                            accum_amount += ask_size
                        else:
                            accum_amount += (self.volume_buy - accum_volume) / ask_price
                            list_ticker.price_buy = self.volume_buy / accum_amount
                            list_ticker.amount_buy = accum_amount
                            break
                        self.KRW -= self.volume_buy
                        if self.KRW < 0:
                            print(f'minus : {self.KRW}')
                            self.KRW = 0
                else:
                    try:
                        order = self.trade_upbit.buy_market_order(list_ticker.ticker, self.volume_buy * 0.9994)
                        print('fail 0.9994')
                    except Exception as e:
                        self.msg = f'buy ticker fail\n{self.trading}({self.id}) {list_ticker.ticker}\n{traceback.print_exc()}'
                        print(self.msg)
                        order = self.trade_upbit.buy_market_order(list_ticker.ticker, self.volume_buy - self.margin_money)
                    uuid = order['uuid']
                    print('UUID :', uuid)
                    while True:
                        print('trade waiting...')
                        time.sleep(1.0)
                        if self.trading == 'upbit':
                            order = self.trade_upbit.get_order(uuid)
                            print(order)
                            if order['state'] == 'cancel' or order['state'] == 'done':
                                list_ticker.amount_buy = float(order['executed_volume'])
                                print(order['state'])
                                break
                self.free_portion -= list_ticker.portion
                self.free_portion = round(self.free_portion, 1)
                print('order complete')
                self.msg += 'order complete'
                trade_time = datetime.datetime.now().timestamp()
                average = list_ticker.price_buy
                amount = list_ticker.amount_buy
                self.msg = f'###################\ntrade complete : {list_ticker.ticker}\n{self.trading}({self.id})\nprice : {average:,.2f}\namount : {amount}\n###################'
                temp = pd.DataFrame(columns=self.column_trading)
                temp = temp.append(pd.Series(dtype=float, name=0))
                temp.iloc[0]['timestamp'] = trade_time
                temp.iloc[0]['ticker'] = list_ticker.ticker
                temp.iloc[0]['period_MA1'] = list_ticker.MA1_period
                temp.iloc[0]['period_MA2'] = list_ticker.MA2_period
                temp.iloc[0]['period_MA_flow'] = list_ticker.MA_flow_period
                temp.iloc[0]['side'] = 'buy'
                temp.iloc[0]['MA1'] = list_ticker.MA1
                temp.iloc[0]['MA2'] = list_ticker.MA2
                temp.iloc[0]['MA_flow'] = list_ticker.MA_flow
                temp.iloc[0]['price buy'] = average
                temp.iloc[0]['amount buy'] = amount
                temp.set_index('timestamp', inplace=True)
                self.list_trade = self.list_trade.append(temp)
                print('save trade data')
                self.list_trade.to_csv(self.file_nm)
                return True
        except Exception as e:
            self.msg = f'buy ticker fail\n{self.trading}({self.id}) {list_ticker.ticker}\n{traceback.print_exc()}'
            print(self.msg)
            return False

    def sell_ticker(self, list_ticker):
        try:
            if list_ticker.MA1 < list_ticker.MA2 and list_ticker.pre_MA1 > list_ticker.pre_MA2:
                print(f'selling start : {self.trading}({self.id}) {list_ticker.ticker}\n')
                amount_sell = list_ticker.amount_buy
                if self.ex_mode:
                    orderbook = pd.DataFrame(pyupbit.get_orderbook(ticker=list_ticker.ticker))
                    print('orderbook',len(orderbook))
                    accum_amount = 0
                    sum_bid = 0
                    for i in range(0,len(orderbook),1):
                        bid_price = orderbook.iloc[i]['orderbook_units']['bid_price']
                        bid_size = orderbook.iloc[i]['orderbook_units']['bid_size']
                        if accum_amount + bid_size < list_ticker.amount_buy:
                            accum_amount += bid_size
                            sum_bid += bid_price * bid_size
                        else:
                            bid_size = list_ticker.amount_buy - accum_amount
                            sum_bid += bid_price * bid_size
                            average = sum_bid/list_ticker.amount_buy
                            break
                    self.KRW += sum_bid

                else:
                    print(f'selling : amount sell {amount_sell}')
                    order = self.trade_upbit.sell_market_order(list_ticker.ticker, amount_sell)
                    uuid = order['uuid']
                    while True:
                        print('trade waiting...')
                        time.sleep(0.05)
                        order = self.trade_upbit.get_order(uuid)
                        if order['state'] == 'cancel' or order['state'] == 'done':
                            print(order['state'])
                            break
                    print('order sell : ',order)
                    average = list_ticker.price_now
                self.msg = f'###################\nsell complete : {list_ticker.ticker}\n{self.trading}({self.id})\nprice : {average:,.2f}\namount : {amount_sell}\n###################'
                temp = pd.DataFrame(columns=self.column_trading)
                temp = temp.append(pd.Series(dtype=float, name=0))
                temp.iloc[0]['timestamp'] = datetime.datetime.now().timestamp()
                temp.iloc[0]['ticker'] = list_ticker.ticker
                temp.iloc[0]['period_MA1'] = list_ticker.MA1_period
                temp.iloc[0]['period_MA2'] = list_ticker.MA2_period
                temp.iloc[0]['period_MA_flow'] = list_ticker.MA_flow_period
                temp.iloc[0]['side'] = 'sell'
                temp.iloc[0]['MA1'] = list_ticker.MA1
                temp.iloc[0]['MA2'] = list_ticker.MA2
                temp.iloc[0]['MA_flow'] = list_ticker.MA_flow
                temp.iloc[0]['price sell'] = average
                temp.iloc[0]['amount buy'] = amount_sell
                temp.set_index('timestamp', inplace = True)
                self.list_trade = self.list_trade.append(temp)
                print('save trade data')
                self.list_trade.to_csv(self.file_nm)
                self.free_portion += list_ticker.portion
                self.free_portion = round(self.free_portion, 1)
                list_ticker.amount_buy = 0
                return 1, average
            else:
                return 2, 0
        except Exception:
            print(f'selling fail : {traceback.print_exc()}')
            return 9, 0


class main():
    def __init__(self):
        super().__init__()
        self.set_hour = 9
        self.set_minute = 0

        self.tele_message = False

        self.total = 0

        self.num_bot = 0
        self.num_ticker = 0
        self.flag_done_init = 0
        self.path_result = './result.csv'

        self.bot = []

        self.column_result = ['timestamp', 'time', 'TOTAL', 'ror', 'hpr']

        ###초기화 함수
        self.open_file()
        self.init_telegram()
        self.pre_hour = datetime.datetime.now().hour

        for i in range(0, self.num_bot):
            msg = f'ex mode : {self.bot[i].ex_mode}'
            if self.bot[i].ex_mode:
                msg = 'it is exMode'
                print(msg)
                self.tele_bot.send_message(chat_id=self.mc, text=msg)
            print(msg)
            self.tele_bot.send_message(chat_id=self.mc, text=msg)
            self.init_time(self.bot[i], self.set_hour, self.set_minute)
            for ticker__ in self.bot[i].list_ticker:
                self.bot[i].set_value(ticker__)
                self.bot[i].check_trade(ticker__)
                if ticker__.flag_sys == 1:
                    if ticker__.MA1 > ticker__.MA2:
                        ticker__.status = 'waiting'
                    else:
                        ticker__.status = 'buying'
                elif ticker__.flag_sys == 2:
                    ticker__.status = 'selling'
                try:
                    self.tele_bot.send_message(chat_id=self.mc, text=self.bot[i].msg)
                except Exception:
                    print(f'{ticker__.ticker} is not bought')
                self.num_ticker += 1

        # ------------ 타이머 START
        self.clock1()  # 메인 시퀀스

    def clock1(self):  # 타이머
        try:
            if not datetime.datetime.now().hour == self.pre_hour:
                print(datetime.datetime.now())
                time.sleep(10)
                self.pre_hour = datetime.datetime.now().hour
                for ibot in self.bot:
                    for ticker__ in ibot.list_ticker:
                        ticker__.to_work = True

            for ibot in self.bot:
                if datetime.datetime.now() > ibot.next_time:  # 오전 9시 현재 값 저장
                    msg = f"{ibot.trading}\nit's set time {datetime.datetime.now()}"
                    print(msg)
                    self.init_time(ibot, self.set_hour, self.set_minute)
                    for ticker__ in ibot.list_ticker:
                        print(f'flag_sys start : {ticker__.flag_sys} {ticker__.ticker}')
                        self.flag_done_init += 1
                for ticker__ in ibot.list_ticker:
                    if ticker__.to_work:
                        ticker__.to_work = False
                        time.sleep(1)
                        self.time_cur = datetime.datetime.now()
                        tmp = pyupbit.get_ohlcv(ticker__.ticker)
                        ticker__.price_now = tmp.iloc[-1]['close']

                        time.sleep(0.1)
                        ibot.set_value(ticker__)
                        if ticker__.MA_flow > ticker__.pre_MA_flow and ticker__.prepre_MA_flow > ticker__.pre_MA_flow:  #추세가 +로 전환될 때 알림
                            self.tele_bot.send_message(chat_id=self.mc, text='+ 추세 전환')

                        if ticker__.flag_sys == 1:  # seaching...
                            ticker__.flag_sys = ibot.searching(ticker__)
                            if ticker__.flag_sys == 2:
                                self.tele_bot.send_message(chat_id=self.mc, text=ibot.msg)
                                print(ibot.msg)
                            if ticker__.flag_sys == 9:     #buy 실패일때 텔레그램 메세지 송부를 위함
                                self.tele_bot.send_message(chat_id=self.mc, text=ibot.msg)
                                print(ibot.msg)
                                ticker__.flag_sys = 1
                        elif ticker__.flag_sys == 2:  # sell timing 탐색
                            ticker__.flag_sys, ticker__.price_sell = ibot.sell_ticker(ticker__)
                            if ticker__.flag_sys == 1:
                                print(ibot.msg)
                                ticker__.ror = ticker__.price_sell / ticker__.price_buy
                                msg = f'###################\nticker : {ticker__.ticker}\nprice buy : {ticker__.price_buy}\nprice sell : {ticker__.price_sell}\nror : {(ticker__.ror - 1)*100:,.2f}\n###################'
                                self.tele_bot.send_message(chat_id=self.mc, text=msg)
                                ticker__.price_buy = 0.0
                                ticker__.price_sell = 0.0
                            elif ticker__.flag_sys == 9:     #buy 실패일때 텔레그램 메세지 송부를 위함
                                self.tele_bot.send_message(chat_id=self.mc, text=ibot.msg)
                                print(ibot.msg)
                                ticker__.flag_sys = 1
                        if ticker__.flag_sys == 1:
                            if ticker__.MA1 > ticker__.MA2:
                                ticker__.status = 'waiting'
                            else:
                                ticker__.status = 'buying'
                        elif ticker__.flag_sys == 2:
                            ticker__.status = 'selling'
            if self.flag_done_init == self.num_ticker:  #9시 정각 모든 티커가 셀링 되었을 때
                self.flag_done_init = 0
                print('day result calculating...')
                self.total, value_balance, msg = self.calculate_balance()
                now = self.bot[0].now_time - datetime.timedelta(days=1)
                try:
                    self.result = pd.read_csv(self.path_result)
                    print(self.result)
                    tmp_ror = self.total / self.result.iloc[-1]['TOTAL'] - 1
                    tmp_columns = self.column_result

                    for col in value_balance:
                        if not col in tmp_columns:
                            tmp_columns.append(col)

                    for col in self.result.columns:
                        if not col in tmp_columns:
                            tmp_columns.append(col)

                    for item in tmp_columns:
                        if not item in self.result.columns:
                            self.result[item] = 0

                    tmp_data = pd.DataFrame()
                    tmp_data = tmp_data.append(pd.Series(dtype=float, name=0))

                    for item in tmp_columns:
                        if item == 'timestamp':
                            tmp_data['timestamp'] = now.timestamp()
                        elif item == 'time':
                            tmp_data['time'] = now
                        elif item == 'TOTAL':
                            tmp_data['TOTAL'] = self.total
                        elif item == 'KRW':
                            KRW = 0
                            for ibot in self.bot:
                                KRW += ibot.KRW
                            tmp_data['KRW'] = KRW
                        elif item == 'ror':
                            tmp_data['ror'] = tmp_ror
                        elif item == 'hpr':
                            tmp_data['hpr'] = self.result.iloc[-1]['hpr'] * (tmp_ror + 1)
                        elif item == 'cum_hpr':
                            print('cum_hpr')
                            tmp_data['cum_hpr'] = self.result.iloc[-1]['cum_hpr'] * (tmp_ror + 1)
                        else:
                            if item in value_balance.keys():
                                tmp_data[item] = value_balance[item]
                            else:
                                tmp_data[item] = 0

                    print(f'tmp_columns : {tmp_columns}')
                    print(tmp_data)

                    self.result = self.result.append(tmp_data, ignore_index=True)
                    self.result['MDD'] = (self.result['cum_hpr'].cummax() - self.result['cum_hpr']) / self.result['cum_hpr'].cummax() * 100
                    self.result = self.result[tmp_columns]
                    self.result.to_csv(self.path_result, index=False)
                except Exception as e:
                    print(traceback.print_exc())
                    msg += 'error' + traceback.print_exc()
                print('day result calculating done')
                # msg += f'총합 : {int(self.total):,}\n노김프 : {int(self.total_nop):,}'
                msg += f'\n수익 : {self.result.iloc[-1]["ror"] * 100:,.2f}%\nDD : {self.result.iloc[-1]["MDD"]:,.2f}% (MAX {self.result["MDD"].max():,.2f}%)\n원금대비 : {format(int(self.result.iloc[-1]["TOTAL"] - self.result["CASH"].sum()), ",")}원'
                print(msg)
                self.tele_bot.send_message(chat_id=self.mc, text=msg)
            self.updater.start_polling()  # 텔레그램 메신저 리시버 콜
        except Exception as e:
            time.sleep(5)
            print("failed clock loop: ", traceback.print_exc())
        self.timer1 = threading.Timer(1.0, self.clock1).start()


    def init_time(self, bot, set_hour, set_minute):
        now = datetime.datetime.now()
        bot.next_time = datetime.datetime(now.year, now.month, now.day, set_hour, set_minute)
        if now > bot.next_time:
            bot.next_time = bot.next_time + datetime.timedelta(days=1)
        bot.now_time = bot.next_time - datetime.timedelta(days=1)

    def open_file(self):
        for i in os.listdir():
            if i[:3] == 'api':
                list_ticker = list()
                list_MA1 = list()
                list_MA2 = list()
                list_MA_flow = list()
                list_portion = list()
                id = i.split('_')[2].split('.')[0]
                with open(i) as f:
                    lines = f.readlines()
                for k in range(4,len(lines)):
                    list_ticker.append(lines[k].split('_')[0])
                    list_MA1.append(int(lines[k].split('_')[1]))
                    list_MA2.append(int(lines[k].split('_')[2]))
                    list_MA_flow.append(int(lines[k].split('_')[3]))
                    list_portion.append(float(lines[k].split('_')[4]))
                print(list_ticker)
                trading = lines[0].strip()
                ex_mode = lines[1].strip()
                if ex_mode == 'True':
                    ex_mode = True
                else:
                    ex_mode = False
                key = lines[2].strip()
                secret = lines[3].strip()
                self.bot.append(self.init_API(key, secret, id, trading, ex_mode, list_ticker, list_MA1, list_MA2, list_MA_flow, list_portion))

            elif i[:8] == 'telegram':
                with open(i) as f:
                    lines = f.readlines()
                self.mc = lines[0]
                self.Token = lines[2]
                if lines[1] == 'True\n':
                    self.tele_message = True
                    print('tele message is True')
                else:
                    print('tele message is False')
        self.num_bot = len(self.bot)
        print(f'num of bot : {self.num_bot}')


    def init_API(self, key, secret, id, trading, ex_mode, list_ticker, list_MA1, list_MA2, list_MA_flow, list_portion):
        try:
            temp_bot = TradingBot()
            temp_bot.trading = trading
            temp_bot.ex_mode = ex_mode
            temp_bot.trade_upbit = pyupbit.Upbit(key,secret)
            temp_bot.margin_money = 100000
            temp_bot.id = id
            for tick, MA1, MA2, MA_flow, portion in zip(list_ticker, list_MA1, list_MA2, list_MA_flow, list_portion):
                tmp_ticker = bot_ticker()
                tmp_ticker.ticker = tick
                tmp_ticker.MA1_period = MA1
                tmp_ticker.MA2_period = MA2
                tmp_ticker.MA_flow_period = MA_flow
                tmp_ticker.portion = portion
                temp_bot.list_ticker.append(tmp_ticker)
            msg = f'{temp_bot.trading} 로그인'
            temp_bot.file_nm = f'trade_list_{temp_bot.id}.csv'
            list_dir = os.listdir()
            if not temp_bot.file_nm in list_dir:
                temp_bot.list_trade = pd.DataFrame(columns=temp_bot.column_trading)
                temp_bot.list_trade.set_index('timestamp', inplace=True)
                temp_bot.list_trade.to_csv(temp_bot.file_nm)
                print('new trade list\n', temp_bot.list_trade)
            else:
                temp_bot.list_trade = pd.read_csv(temp_bot.file_nm)
                temp_bot.list_trade.set_index('timestamp', inplace=True)
                print(temp_bot.list_trade)

            if ex_mode:
                result = pd.read_csv(self.path_result)
                temp_bot.KRW = int(result.iloc[-1]['KRW'])
                print(f'현재 KRW : {temp_bot.KRW}')

            print(msg)
            return temp_bot
        except Exception as e:
            print(traceback.print_exc())

    def calculate_balance(self):
        try:
            value_temp = {}
            total = 0
            msg = ''
            for ibot in self.bot:
                t1, temp_msg = self.calculate_ibot(ibot)
                msg += temp_msg
                total += t1
                value_temp[ibot.id] = t1
                # msg += f'{ibot.id} {int(t1)}원\n'
            msg += f'#########\n총액 : {int(total):,}원\n'
            result = pd.read_csv(self.path_result)
            msg += f'DD : {result.iloc[-1]["MDD"]:,.2f}% (MAX {result["MDD"].max():,.2f}%)\n원금대비 : {format(int(result.iloc[-1]["TOTAL"] - result["CASH"].sum()), ",")}원'
            return total,value_temp,msg
        except Exception as e:
            print(f'fail calulate balance {e}')
            print(traceback.print_exc())

    def calculate_ibot(self,nowbot):
        tt = 0
        msg = ''
        if nowbot.ex_mode:
            print('ex Mode\n')
            msg += f'{nowbot.trading}({nowbot.id})\n'
            print(msg)
            for ticker__ in nowbot.list_ticker:
                try:
                    ticker__.balance_base = ticker__.amount_buy
                except Exception as e:
                    print(f'{ticker__.ticker.split("-")[1]} balance empty')
                    ticker__.balance_base = 0
                tmp_ticker1 = ticker__.ticker.split('-')[1]
                tmp_balance1 = ticker__.balance_base
                tmp_price = pyupbit.get_orderbook(ticker=ticker__.ticker)['orderbook_units'][0]['ask_price']
                tt += tmp_balance1 * tmp_price
                msg += f'   {tmp_ticker1} : {tmp_balance1} (KRW : {int(tmp_balance1 * tmp_price)})\n'
            ticker__.balance_quote = nowbot.KRW
            tt += ticker__.balance_quote
        else:
            msg += f'{nowbot.trading}({nowbot.id})\n'
            print(msg)
            for ticker__ in nowbot.list_ticker:
                try:
                    # ticker__.balance_base = nowbot.trade_upbit.get_balance(ticker__.ticker)
                    ticker__.balance_base = ticker__.amount_buy
                except Exception as e:
                    print(f'{ticker__.ticker.split("-")[1]} balance empty')
                    ticker__.balance_base = 0
                tmp_ticker1 = ticker__.ticker.split('-')[1]
                tmp_balance1 = ticker__.balance_base
                tmp_price = pyupbit.get_orderbook(ticker=ticker__.ticker)['orderbook_units'][0]['ask_price']
                print(tmp_balance1,type(tmp_balance1))
                print(tmp_price,type(tmp_price))
                tt += tmp_balance1 * tmp_price
                msg += f'- {tmp_ticker1} {ticker__.MA1_period}/{ticker__.MA2_period}  {tmp_balance1} (KRW : {int(tmp_balance1 * tmp_price):,}원)\n'
            ticker__.balance_quote = nowbot.trade_upbit.get_balance('KRW')
            tt += ticker__.balance_quote
        msg += f'KRW : {int(ticker__.balance_quote):,}원\n'
        msg += f'Total : {int(tt):,}원\n'
        print(msg)
        return tt, msg

    def init_telegram(self):    # 텔레그램봇 초기화
        self.tele_bot = telegram.Bot(token=self.Token)
        self.updater = Updater(token=self.Token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        message_handler = MessageHandler(filters=Filters.text & (~Filters.command), callback=self.receive_message)
        self.dispatcher.add_handler(message_handler)    # 메세지 handler 추가

    def receive_message(self, update, context):  # 아무 메세지를 받으면 실행
        try:
            print(f'receive message : {update.message.text}')
            if update.message.text == '1':  # 현재가격 계산
                for ibot in self.bot:
                    msg = f'{ibot.trading}({ibot.id})'
                    print(msg)
                    context.bot.send_message(chat_id=self.mc, text=msg)
                    for ticker__ in ibot.list_ticker:
                        msg = f'# {ticker__.ticker}({ticker__.portion}) {ticker__.MA1_period}/{ticker__.MA2_period} {ticker__.MA_flow_period} {ticker__.status}\n- MA1 {ticker__.MA1_period} : {int(ticker__.MA1):,}\n- MA2 {ticker__.MA2_period} : {int(ticker__.MA2):,}\n'
                        if ticker__.MA_flow > ticker__.pre_MA_flow:
                            direction = '+'
                        else:
                            direction = '-'
                        msg += f'- MA_flow {ticker__.MA_flow_period} {int(ticker__.MA_flow):,} ({direction})\n'
                        tmp_price = pyupbit.get_orderbook(ticker=ticker__.ticker)['orderbook_units'][0]['ask_price']
                        msg += f'- price now : {int(tmp_price):,}'
                        if ticker__.status == 'selling':
                            msg += f'\n- price buy: {ticker__.price_buy:,.3f}\n-profit : {(tmp_price / ticker__.price_buy - 1) * 100:,.2f}%'
                        print(msg)
                        context.bot.send_message(chat_id=self.mc, text=msg)
            elif update.message.text == '2':  # 잔고 계산
                t1, temp_balance, msg = self.calculate_balance()
                print(msg)
                context.bot.send_message(chat_id=self.mc, text=msg)
            elif update.message.text == '3':  # 김프 계산
                msg = f'ex mode :'
                print(msg)
                context.bot.send_message(chat_id=self.mc, text=msg)
            elif update.message.text == '4':  # 원하는 정보
                msg = ''
                for ibot in self.bot:
                    msg += f'{ibot.trading} {len(ibot.list_ticker)} ,free portion : {ibot.free_portion}\n'
                print(msg)
                context.bot.send_message(chat_id=self.mc, text=msg)
            elif update.message.text == 'ㅋ':  # 원하는 정보
                msg = "I'm alive~!!!"
                context.bot.send_message(chat_id=self.mc, text=msg)
        except Exception as e:
            print(f'telegram : ',traceback.print_exc())

if __name__ == '__main__':
    #print_hi('PyCharm')
    main()
