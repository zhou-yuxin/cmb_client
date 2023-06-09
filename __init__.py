import re
import time
import logging
import uiautomator2

from decimal import Decimal

class Client:

    PACKAGE_NAME = "cmb.pb"

    def __init__(self, app_password, trans_password, addr = None, imp_wait = 15):
        device = uiautomator2.connect(addr)
        device.implicitly_wait(imp_wait)
        device.set_fastinput_ime(True)
        device.app_start(self.PACKAGE_NAME, wait = True)
        self._device = device
        self._app_password = app_password
        self._trans_password = trans_password

    def __del__(self):
        # self._device.app_stop(self.PACKAGE_NAME)
        pass

    def _routine(self, func):
        start_time = time.time()
        last_match_time = start_time
        while True:
            time.sleep(1)
            ret = func()
            if ret == True:
                return True
            current = time.time()
            if current - start_time > self._device.wait_timeout * 8:
                break
            if ret == None:
                last_match_time = current
            else:
                assert(ret == False)
                if current - last_match_time > self._device.wait_timeout:
                    break
        self._device.screenshot("cmb_unmatched.png")
        xml = self._device.dump_hierarchy()
        fd = open("cmb_unmatched.xml", "w")
        fd.write(xml)
        fd.close()
        return False

    def _element(self, **kwargs):
        if "resourceId" in kwargs:
            value:str = kwargs["resourceId"]
            if value.startswith("/"):
                value = value[1:]
            else:
                value = self.PACKAGE_NAME + ":id/" + value
            kwargs["resourceId"] = value
        return self._device(**kwargs)

    def _exist(self, **kwargs):
        return self._element(enabled = True, **kwargs).exists

    def _existAll(self, **kwargs):
        for (key, values) in kwargs.items():
            for value in (values if isinstance(values, (list, tuple)) else (values,)):
                if not self._exist(**{key: value}):
                    return False
        return True

    def _click(self, offset = None, **kwargs):
        self._element(**kwargs).click(offset = offset)

    def _setText(self, string, **kwargs):
        self._element(**kwargs).set_text(string)

    class Password:

        def __init__(self, client, password):
            self._client = client
            self._password = password
            self._is_first = True

        def input(self):
            client: Client = self._client
            if not client._exist(resourceId = "customkeyboard_view"):
                return False
            if not self._is_first:
                for _ in range(len(self._password) + 1):
                    client._click(description = "删除")
            for n in self._password:
                if not ("0" <= n <= "9"):
                    raise ValueError("键盘输入仅支持数字")
                client._click(text = n, className = "android.widget.Button")
            client._click(text = "完成", resourceId = "cmbkb_tvComplete")
            self._is_first = False
            return True

    def _isIndex(self):
        return self._exist(description = "扫一扫，按钮")

    def _gotoZZY2(self, action, target):
        is_ad_in_index = lambda: self._existAll(description = ("活动图片，双击后打开活动页面", "关闭"))
        is_login = lambda: self._exist(text = "短信安全登录")
        is_zzy2 = lambda: self._existAll(text = ("朝朝盈2号", "了解朝朝盈2号"))
        password = Client.Password(self, self._app_password)
        def func():
            nonlocal password
            if target():
                return True
            elif is_zzy2():
                self._click(text = action)
            elif self._isIndex():
                self._click(text = "朝朝盈2号")
            elif is_ad_in_index():
                self._click(description = "关闭")
            elif password.input():
                self._click(text = "登录")
            elif is_login():
                self._click(resourceId = "editPassword")
            else:
                return False
        if not self._routine(func):
            raise RuntimeError("进入<朝朝盈2号-%s>失败" % action)

    def _goHome(self):
        btn_more = {"descriptionMatches": "更多.*，按钮"}
        btn_index = {"text": "首页", "resourceId": "tvMenuItem"}
        def func():
            if self._isIndex():
                return True
            elif self._exist(**btn_index):
                self._click(**btn_index)
            elif self._exist(**btn_more):
                self._click(**btn_more)
            else:
                return False
        if not self._routine(func):
            raise RuntimeError("回到<首页>失败")

    def _extractMoney(self, rexp: str):
        rexp = rexp.replace("<$>", "[\\d,\\.]+")
        text = self._element(textMatches = rexp).get_text()
        text:str = re.findall(rexp, text)[0]
        return Decimal(text.replace(",", ""))

    def _toMoneyString(self, money):
        return 
        


    def buyZZY2(self, max_money = None):
        is_buy_zzy2 = lambda: self._exist(textContains = "提交后，结合持仓智能分配转入金额")
        self._gotoZZY2("转入", is_buy_zzy2)
        is_confirm = lambda: self._exist(textContains = "购买确认后，")
        is_input_password = lambda: self._exist(text = "请输入取款密码")
        is_result = lambda: self._exist(text = "您的交易委托已受理")
        password = Client.Password(self, self._trans_password)
        money = None
        def func():
            nonlocal password, money
            if is_buy_zzy2():
                available = self._extractMoney("账户.*可用余额[^\\d]+(<$>)元")
                if max_money is None:
                    money = available
                else:
                    money = min(Decimal("%.2f" % max_money), available)
                if money == 0:
                    return True
                (_, _, _, y1) = self._element(text = "转入金额").bounds()
                (_, y2, _, _) = self._element(textContains = "提交后，结合持仓智能").bounds()
                self._device.click(0.5, int((y1 + y2) / 2))
                str_money = str(money)
                for _ in range(len(str_money) + 1):
                    self._device.press("del")
                for c in str_money:
                    self._device.send_keys(c)
                self._click(text = "下一步")
            elif password.input():
                self._click((0.5, 0.95), className = "android.app.Dialog")
            elif is_input_password():
                self._click(resourceId = "/owl_remit_pwd_")
            elif is_confirm():
                if self._exist(textContains = "转入金额{:,.2f}元".format(money)):
                    self._click(className = "android.widget.CheckBox")
                    self._click(text = "确定转入")
                else:
                    self._click(description = "返回，按钮")
            elif is_result():
                self._click(text = "完成")
                return True
            else:
                return False
        if not self._routine(func) or money is None:
            raise RuntimeError("转入朝朝盈2号失败")
        logging.info("已向朝朝盈2号转入%s元..." % money)
        self._goHome()
        return money

    def sellZZY2(self, max_money = None):
        is_sell_zzy2 = lambda: self._exist(text = "快速转出(当日无收益)")
        self._gotoZZY2("转出", is_sell_zzy2)
        is_input_password = lambda: self._exist(text = "请输入取款密码")
        is_confirm = lambda: self._exist(text = "《招商银行代销货币基金快速赎回服务协议》")
        is_result = lambda: self._exist(text = "您的交易委托已受理")
        password = Client.Password(self, self._trans_password)
        money = None
        def func():
            nonlocal password, money
            if is_sell_zzy2():
                available = self._extractMoney("(<$>)元")
                if max_money is None:
                    money = available
                else:
                    money = min(Decimal("%.2f" % max_money), available)
                if money == 0:
                    return True
                self._setText(str(money), className = "android.widget.EditText")
                self._click(text = "下一步")
            elif password.input():
                self._click((0.5, 0.95), className = "android.app.Dialog")
            elif is_input_password():
                self._click(resourceId = "/owl_remit_pwd_")
            elif is_confirm():
                if self._exist(text = "{:,.2f}".format(money)):
                    self._element(text = "已阅读并同意").left(text = "", clickable = True).click()
                    self._click(text = "确认转出")
                else:
                    self._click(description = "返回，按钮")
            elif is_result():
                self._click(text = "完成")
                return True
            else:
                return False
        if not self._routine(func) or money is None:
            raise RuntimeError("转出朝朝盈2号失败")
        logging.info("已从朝朝盈2号转出%s元..." % money)
        self._goHome()
        return money
