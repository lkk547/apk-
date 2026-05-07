"""
手机炒股模拟器 - Kivy 完整版
功能：真实A股数据（baostock）、随机非ST股票池、K线图、MACD、模拟买卖、交易记录
运行前请安装：pip install kivy baostock pandas
"""

import kivy
kivy.require('2.1.0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.utils import platform
from datetime import datetime, timedelta
import random
import threading

# ----------------------------- 导入 baostock -----------------------------
try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except ImportError:
    BAOSTOCK_AVAILABLE = False
    print("警告: 未安装 baostock，请执行 pip install baostock")

# 窗口设置
if platform in ('android', 'ios'):
    Window.fullscreen = True
else:
    Window.size = (360, 800)
Window.clearcolor = (0.07, 0.09, 0.12, 1)


# ========================== 真实数据获取 ==========================
def fetch_stock_data_from_baostock(code_original, start_date, end_date):
    """从baostock获取真实股票日K线数据（不复权）"""
    if not BAOSTOCK_AVAILABLE:
        return None, "baostock 库未安装，请先安装：pip install baostock"

    # 格式化代码
    if code_original.startswith('6'):
        code = f"sh.{code_original}"
    elif code_original.startswith('0') or code_original.startswith('3'):
        code = f"sz.{code_original}"
    else:
        code = code_original

    try:
        lg = bs.login()
        if lg.error_code != '0':
            bs.logout()
            return None, f"登录失败: {lg.error_msg}"

        rs = bs.query_history_k_data_plus(
            code,
            "date,open,high,low,close,volume,turn",
            start_date=start_date, end_date=end_date,
            frequency="d", adjustflag="3"
        )
        if rs.error_code != '0':
            bs.logout()
            return None, f"查询失败: {rs.error_msg}"

        data_list = []
        while rs.next():
            row = rs.get_row_data()
            try:
                data_list.append({
                    'date': datetime.strptime(row[0], "%Y-%m-%d"),
                    'open': float(row[1]),
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': int(float(row[5])) if row[5] else 0,
                    'turnover': float(row[6]) if row[6] else 0.0
                })
            except:
                continue
        bs.logout()

        if not data_list:
            return None, "所选日期范围内无交易数据"
        return data_list, None
    except Exception as e:
        if 'bs' in locals():
            bs.logout()
        return None, f"网络异常: {str(e)}"


def get_non_st_stock_pool():
    """从baostock获取所有非ST的A股股票列表（代码 + 名称）"""
    if not BAOSTOCK_AVAILABLE:
        return []

    try:
        lg = bs.login()
        if lg.error_code != '0':
            bs.logout()
            return []

        # query_stock_basic 返回股票代码与名称，适合做随机股池
        rs = bs.query_stock_basic()
        stocks = []
        while rs.next():
            row = rs.get_row_data()
            code = row[0]
            name = row[1]
            stock_type = row[4] if len(row) > 4 else ''
            stock_status = row[5] if len(row) > 5 else ''
            if not code.startswith(('sh.', 'sz.')):
                continue

            # 只保留上交所/深交所的普通A股
            if stock_type != '1' or stock_status != '1':
                continue

            # 只保留常见A股代码段，剔除指数和其它非股票代码
            pure_code = code.split('.')[1]
            if not pure_code.startswith(('000', '001', '002', '003', '300', '301', '600', '601', '603', '605', '688')):
                continue

            stock_name = (name or '').upper()
            if ('ST' in stock_name or
                '*ST' in stock_name or
                '退' in stock_name or
                '指数' in stock_name or
                stock_name.startswith('N') or
                stock_name.startswith('C')):
                continue

            stocks.append({'code': pure_code, 'name': name})
        bs.logout()
        return stocks
    except:
        if 'bs' in locals():
            bs.logout()
        return []


def get_random_non_st_stock():
    """随机返回一只非ST股票（带股票名）"""
    pool = get_non_st_stock_pool()
    if not pool:
        return None, None
    stock = random.choice(pool)
    return stock['code'], stock['name']


def calculate_macd_series(kline_data):
    """计算MACD柱状值（标准12/26/9）"""
    ema_short = None
    ema_long = None
    dea = 0.0
    for item in kline_data:
        close = item['close']
        if ema_short is None:
            ema_short = close
            ema_long = close
            dif = 0.0
        else:
            ema_short = ema_short * 11/13 + close * 2/13
            ema_long = ema_long * 25/27 + close * 2/27
            dif = ema_short - ema_long
        dea = dea * 8/10 + dif * 2/10
        item['macd'] = round((dif - dea) * 2, 2)


def show_popup(title, message, size_hint=(0.8, 0.3)):
    content = Label(text=message)
    apply_chinese_font(content)
    popup = Popup(title=title, content=content, size_hint=size_hint)
    popup.open()
    return popup


def create_metric_card(title_text):
    card = BoxLayout(orientation='vertical', padding=8, spacing=6)
    from kivy.graphics import Color, Rectangle
    with card.canvas.before:
        Color(0.11, 0.14, 0.18, 1)
        rect = Rectangle(pos=card.pos, size=card.size)
    def _update_rect(instance, value):
        rect.pos = instance.pos
        rect.size = instance.size
    card.bind(pos=_update_rect, size=_update_rect)
    card.add_widget(Label(text=title_text, font_size='11sp', color=(0.72,0.78,0.86,1), size_hint_y=0.4))
    value_label = Label(text='--', font_size='16sp', bold=True, size_hint_y=0.6, color=(0.94,0.97,1,1))
    card.add_widget(value_label)
    return card, value_label


from kivy.uix.widget import Widget
from kivy.graphics import Rectangle, Line, Color

# ========================== K线绘图控件 ==========================
class KLineCanvas(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.kline_data = []
        self.current_index = -1
        self.window_size = 34
        # 尺寸或位置变化时重绘
        self.bind(size=self.draw, pos=self.draw)
    
    def set_data(self, data, index):
        self.kline_data = data
        self.current_index = index
        self.draw()
    
    def draw(self, *args):
        self.canvas.clear()
        if not self.kline_data or self.current_index < 0:
            return
        
        w, h = self.width, self.height
        if w < 20 or h < 20:
            return
        
        # 左侧留白用于价格标签，保持适中宽度以免占用过多绘图区
        left, right, top, bottom = 46, 18, 18, 28
        chart_w = w - left - right
        chart_h = h - top - bottom
        
        visible_count = min(self.window_size, len(self.kline_data))
        start_index = max(0, self.current_index - visible_count + 1)
        visible_data = self.kline_data[start_index:self.current_index + 1]
        if not visible_data:
            return
        
        all_prices = [p for d in visible_data for p in (d['high'], d['low'])]
        min_p = min(all_prices) * 0.98 if all_prices else 0
        max_p = max(all_prices) * 1.02 if all_prices else 1
        p_range = max(max_p - min_p, 0.1)
        
        spacing = chart_w / max(len(visible_data), 1)
        bar_width = max(7, spacing * 0.62)
        
        # 🟢 Kivy 画布坐标系默认以 Widget 左下角 (0,0) 为原点
        # 将坐标转换为基于 Widget 的绝对坐标，确保绘制位置随 Widget pos/size 正确定位
        base_x, base_y = self.x, self.y
        with self.canvas:
            # 1. 背景
            Color(0.08, 0.10, 0.15, 1)
            Rectangle(pos=self.pos, size=self.size)

            # 2. 水平网格线（并在左侧绘制对应价格标签）
            grid_color = (0.2, 0.23, 0.3, 0.8)
            label_color = (0.95, 0.95, 0.95, 1)
            for i in range(5):
                y = bottom + (i / 4) * chart_h
                Color(*grid_color)
                Line(points=[base_x + left, base_y + y, base_x + left + chart_w, base_y + y], width=0.8)
                # 价格对应为从底部到顶部线性映射，保留两位小数
                price_v = min_p + (i / 4) * (max_p - min_p)
                price_text = f"{price_v:.2f}"
                try:
                    cl = CoreLabel(text=price_text, font_size=12, font_name='ChineseFont')
                    cl.refresh()
                    tex = cl.texture
                    tx_w, tx_h = tex.size
                    # 使用较亮的颜色作为纹理着色
                    Color(*label_color)
                    Rectangle(texture=tex, pos=(base_x + left - tx_w - 6, base_y + y - tx_h/2), size=tex.size)
                except Exception:
                    pass

            # 3. K线实体与影线
            for i, d in enumerate(visible_data):
                x = base_x + left + (i + 0.5) * spacing
                # Y轴向上递增：最低价靠近 bottom，最高价靠近 h-top
                y_open  = base_y + bottom + chart_h * ((d['open'] - min_p) / p_range)
                y_close = base_y + bottom + chart_h * ((d['close'] - min_p) / p_range)
                y_high  = base_y + bottom + chart_h * ((d['high'] - min_p) / p_range)
                y_low   = base_y + bottom + chart_h * ((d['low'] - min_p) / p_range)

                if d['close'] >= d['open']:
                    Color(0.9, 0.2, 0.2, 1)  # 红涨
                else:
                    Color(0.2, 0.8, 0.2, 1)  # 绿跌

                Line(points=[x, y_high, x, y_low], width=1.6)
                rect_h = abs(y_close - y_open)
                rect_y = min(y_open, y_close)
                Rectangle(pos=(x - bar_width/2, rect_y), size=(bar_width, max(rect_h, 1.0)))

            # 4. 当前交易日高亮虚线
            if visible_data:
                x_current = base_x + left + (len(visible_data) - 0.5) * spacing
                Color(1, 0.8, 0.2, 0.9)
                # 虚线贯穿整个图表区域
                Line(points=[x_current, base_y + bottom, x_current, base_y + h - top], 
                     width=1.5, dash_length=4, dash_offset=2)


# ========================== 副图指标控件（成交量/MACD） ==========================
class IndicatorCanvas(Widget):
    def __init__(self, chart_type='volume', **kwargs):
        super().__init__(**kwargs)
        self.kline_data = []
        self.current_index = -1
        self.chart_type = chart_type
        self.window_size = 34
        self.bind(size=self.draw, pos=self.draw)

    def set_data(self, data, index):
        self.kline_data = data
        self.current_index = index
        self.draw()

    def draw(self, *args):
        self.canvas.clear()
        if not self.kline_data or self.current_index < 0:
            return
        w, h = self.width, self.height
        if w < 20 or h < 20:
            return

        left, right, top, bottom = 12, 12, 10, 10
        panel_w = w - left - right

        visible_count = min(self.window_size, len(self.kline_data))
        start_index = max(0, self.current_index - visible_count + 1)
        current_data = self.kline_data[start_index:self.current_index + 1]
        volumes = [item.get('volume', 0) for item in current_data]
        macd_values = [item.get('macd', 0) for item in current_data]
        max_volume = max(volumes) if volumes else 1
        max_macd_abs = max([abs(v) for v in macd_values], default=0.0)
        # MACD改为窗口内自适应缩放：低波动时自动放大，并保留少量边距
        max_macd = max(max_macd_abs * 1.15, 1e-6)
        spacing = panel_w / max(len(current_data), 1)
        bar_w = max(7, spacing * 0.55)
        bar_w2 = max(5, spacing * 0.32)

        # 🟢 同样使用局部相对坐标系
        # 使用基于 widget 的绝对坐标，避免绘制偏移
        base_x, base_y = self.x, self.y
        with self.canvas:
            Color(0.08, 0.10, 0.15, 1)
            Rectangle(pos=self.pos, size=self.size)

            if self.chart_type == 'volume':
                y_base = bottom
                y_top = h - top
                usable_h = max(y_top - y_base - 6, 1)

                Color(0.18, 0.21, 0.28, 1)
                Line(points=[base_x + left, base_y + y_base, base_x + left + panel_w, base_y + y_base], width=0.8)
                Line(points=[base_x + left, base_y + y_top, base_x + left + panel_w, base_y + y_top], width=0.8)

                for i, item in enumerate(current_data):
                    x = base_x + left + (i + 0.5) * spacing
                    bar_h = (item.get('volume', 0) / max_volume) * usable_h
                    if item['close'] >= item['open']:
                        Color(0.9, 0.3, 0.3, 1)
                    else:
                        Color(0.3, 0.85, 0.35, 1)
                    Rectangle(pos=(x - bar_w/2, base_y + y_base + 3), size=(bar_w, max(bar_h, 1.0)))

            else:  # MACD
                y_base = bottom
                y_top = h - top
                mid_y = y_base + (y_top - y_base) / 2
                usable_h = max((y_top - y_base) / 2 - 6, 1)

                Color(0.18, 0.21, 0.28, 1)
                Line(points=[base_x + left, base_y + y_base, base_x + left + panel_w, base_y + y_base], width=0.8)
                Line(points=[base_x + left, base_y + y_top, base_x + left + panel_w, base_y + y_top], width=0.8)
                Line(points=[base_x + left, base_y + mid_y, base_x + left + panel_w, base_y + mid_y], width=1.0)

                for i, item in enumerate(current_data):
                    hist = item.get('macd', 0)
                    x = base_x + left + (i + 0.5) * spacing
                    bar_h = abs(hist) / max_macd * usable_h
                    if hist >= 0:
                        Color(1.0, 0.45, 0.25, 1)
                        Rectangle(pos=(x - bar_w2/2, base_y + mid_y), size=(bar_w2, max(bar_h, 1.0)))
                    else:
                        Color(0.3, 0.75, 1.0, 1)
                        Rectangle(pos=(x - bar_w2/2, base_y + mid_y - bar_h), size=(bar_w2, max(bar_h, 1.0)))


# ========================== 开始页面 ==========================
class StartScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', padding=20, spacing=15)
        self.app = app
        
        self.add_widget(Label(text=' 炒股模拟器', size_hint_y=0.15, font_size='24sp', bold=True))
        
        mode_box = BoxLayout(orientation='vertical', size_hint_y=0.2, spacing=5)
        mode_box.add_widget(Label(text='选择模式', size_hint_y=0.3, bold=True))
        self.mode_random = Button(text=' 随机股票模式（真实A股）', size_hint_y=0.35)
        self.mode_custom = Button(text=' 用户指定股票模式', size_hint_y=0.35)
        mode_box.add_widget(self.mode_random)
        mode_box.add_widget(self.mode_custom)
        self.add_widget(mode_box)
        
        self.code_input = TextInput(hint_text='输入6位代码 (如 600036 或 000001)', size_hint_y=0.08, disabled=True)
        self.add_widget(self.code_input)
        
        date_box = BoxLayout(orientation='vertical', size_hint_y=0.25, spacing=5)
        date_box.add_widget(Label(text='日期范围', size_hint_y=0.3, bold=True))
        date_row1 = BoxLayout(size_hint_y=0.35)
        date_row1.add_widget(Label(text='起始:', size_hint_x=0.2))
        self.start_input = TextInput(text='2023-01-01', size_hint_x=0.8)
        date_row1.add_widget(self.start_input)
        date_row2 = BoxLayout(size_hint_y=0.35)
        date_row2.add_widget(Label(text='结束:', size_hint_x=0.2))
        self.end_input = TextInput(text='2025-12-25', size_hint_x=0.8)
        date_row2.add_widget(self.end_input)
        date_box.add_widget(date_row1)
        date_box.add_widget(date_row2)
        self.add_widget(date_box)
        
        tip = Label(text='提示: 随机模式会从非ST股票池中自动选股\n建议范围不少于3个月', size_hint_y=0.08, color=(0.7,0.7,0.7,1), font_size='11sp')
        self.add_widget(tip)
        
        self.start_btn = Button(text='🚀 开始模拟', size_hint_y=0.12, background_color=(0.2,0.6,0.9,1))
        self.add_widget(self.start_btn)
        
        self.mode_random.bind(on_press=self.set_random_mode)
        self.mode_custom.bind(on_press=self.set_custom_mode)
        self.start_btn.bind(on_press=self.start_simulation)
        
        self.set_random_mode(None)
        apply_chinese_font(self)
    
    def set_random_mode(self, instance):
        self.mode_random.background_color = (0.3,0.7,1,1)
        self.mode_custom.background_color = (0.2,0.2,0.2,1)
        self.code_input.disabled = True
        self.code_input.text = ''
        self.app.selected_mode = 'random'
    
    def set_custom_mode(self, instance):
        self.mode_custom.background_color = (0.3,0.7,1,1)
        self.mode_random.background_color = (0.2,0.2,0.2,1)
        self.code_input.disabled = False
        self.app.selected_mode = 'custom'
    
    def start_simulation(self, instance):
        start_str = self.start_input.text.strip()
        end_str = self.end_input.text.strip()
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d")
        except:
            show_popup('错误', '日期格式错误，请使用 YYYY-MM-DD')
            return
        if start_date > end_date:
            show_popup('错误', '起始日期不能晚于结束日期')
            return
        
        if self.app.selected_mode == 'custom':
            code = self.code_input.text.strip()
            if not code.isdigit() or len(code) != 6:
                show_popup('错误', '请输入6位数字股票代码')
                return
            self.app.stock_code = code
            self.app.stock_name = '用户指定股票'
        else:
            self.app.stock_code = None
            self.app.stock_name = None
        
        self.app.start_date = start_date
        self.app.end_date = end_date
        self.app.show_main_screen()


# ========================== 主界面（含交易记录） ==========================
class MainScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self.kline_data = []
        self.current_index = 0
        self.initial_capital = 100000.0
        self.cash = self.initial_capital
        self.position = 0
        self.avg_cost = 0.0
        self.current_stock_code = None
        self.current_stock_name = None
        
        # 交易记录列表
        self.transactions = []  # 每条记录: {'time': str, 'stock': str, 'action': str, 'shares': int, 'price': float, 'amount': float, 'profit': float}
        
        # 去除默认布局间距，避免出现额外空白
        self.padding = [0, 0, 0, 0]
        self.spacing = 0

        self.build_ui()
        self.loading_popup = None
        Clock.schedule_once(lambda dt: self._start_data_loading(), 0.1)
    
    def build_ui(self):
        # 顶部股票信息栏
        self.stock_header = BoxLayout(size_hint_y=0.08, padding=[10,5], spacing=8)
        self.back_btn = Button(
            text='返回',
            size_hint_x=0.28,
            size_hint_y=0.82,
            pos_hint={'center_y': 0.5},
            halign='center',
            valign='middle',
            background_color=(0.3,0.5,0.8,1)
        )
        title_box = BoxLayout(orientation='vertical', spacing=0)
        self.stock_name_label = Label(text='加载中...', bold=True, font_size='16sp', halign='left', valign='middle')
        self.stock_code_label = Label(text='', font_size='12sp', color=(0.7,0.7,0.7,1), halign='left', valign='middle')
        self.refresh_btn = Button(
            text='换股',
            size_hint_x=0.25,
            size_hint_y=0.82,
            pos_hint={'center_y': 0.5},
            halign='center',
            valign='middle',
            background_color=(0.3,0.5,0.8,1)
        )
        self.back_btn.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        self.refresh_btn.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        title_box.add_widget(self.stock_name_label)
        title_box.add_widget(self.stock_code_label)
        self.stock_header.add_widget(self.back_btn)
        self.stock_header.add_widget(title_box)
        self.stock_header.add_widget(self.refresh_btn)
        # 先构建各区域，最后按垂直布局的逆序加入，确保顶部到底部顺序正确
        # 指标卡片区
        self.summary_box = BoxLayout(orientation='vertical', size_hint_y=0.15, padding=[8,6], spacing=4)
        header_row = BoxLayout(size_hint_y=0.3, spacing=8)
        self.prev_btn = Button(text='前一天', size_hint_x=0.23)
        self.date_label = Label(text='交易日: --', bold=True, font_size='15sp')
        self.next_btn = Button(text='后一天', size_hint_x=0.23)
        header_row.add_widget(self.prev_btn)
        header_row.add_widget(self.date_label)
        header_row.add_widget(self.next_btn)
        self.summary_box.add_widget(header_row)
        
        metrics_grid = GridLayout(cols=3, spacing=6, size_hint_y=0.7)
        card1, self.price_label = create_metric_card('当日价格')
        card2, self.change_label = create_metric_card('涨幅')
        card3, self.high_label = create_metric_card('最高')
        card4, self.low_label = create_metric_card('最低')
        card5, self.open_label = create_metric_card('开盘价')
        card6, self.turnover_label = create_metric_card('换手率')
        for card in [card1,card2,card3,card4,card5,card6]:
            metrics_grid.add_widget(card)
        self.summary_box.add_widget(metrics_grid)
        self.kcanvas = KLineCanvas(size_hint_y=0.30)

        volume_box = BoxLayout(orientation='vertical', size_hint_y=0.13, padding=[8,2], spacing=1)
        volume_title = Label(text='成交量', size_hint_y=0.25, bold=True, font_size='13sp')
        self.volume_canvas = IndicatorCanvas(chart_type='volume', size_hint_y=0.75)
        volume_box.add_widget(volume_title)
        volume_box.add_widget(self.volume_canvas)

        macd_box = BoxLayout(orientation='vertical', size_hint_y=0.13, padding=[8,2], spacing=1)
        macd_title = Label(text='MACD', size_hint_y=0.25, bold=True, font_size='13sp')
        self.macd_canvas = IndicatorCanvas(chart_type='macd', size_hint_y=0.75)
        macd_box.add_widget(macd_title)
        macd_box.add_widget(self.macd_canvas)
        
        trade_box = BoxLayout(orientation='vertical', size_hint_y=0.11, padding=[8,4], spacing=4)
        self.status_label = Label(
            text='点击买入或卖出',
            size_hint_y=0.36,
            font_size='11sp',
            color=(0.94,0.96,1,1),
            halign='center',
            valign='middle'
        )
        # 确保多行对齐生效
        self.status_label.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        trade_box.add_widget(self.status_label)
        btn_row = BoxLayout(size_hint_y=0.64, spacing=8)
        self.buy_btn = Button(text='买入', background_color=(0.2,0.8,0.2,1))
        self.sell_btn = Button(text='卖出', background_color=(0.9,0.2,0.2,1))
        # 交易记录按钮（替代原“查看持仓”）
        self.history_btn = Button(text='交易记录', background_color=(0.25,0.45,0.85,1))
        btn_row.add_widget(self.buy_btn)
        btn_row.add_widget(self.sell_btn)
        btn_row.add_widget(self.history_btn)
        trade_box.add_widget(btn_row)
        
        self.prev_btn.bind(on_press=self.prev_day)
        self.next_btn.bind(on_press=self.next_day)
        self.buy_btn.bind(on_press=self.buy)
        self.sell_btn.bind(on_press=self.sell)
        self.history_btn.bind(on_press=self.show_transaction_history)
        self.back_btn.bind(on_press=self.go_back_to_start)
        self.refresh_btn.bind(on_press=self.random_stock)
        
        self.add_widget(self.stock_header)
        self.add_widget(self.summary_box)
        self.add_widget(self.kcanvas)
        self.add_widget(volume_box)
        self.add_widget(macd_box)
        self.add_widget(trade_box)
        apply_chinese_font(self)
    
    def add_transaction(self, action, shares, price, amount, profit=0.0):
        """添加一条交易记录"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stock_name = self.current_stock_name if self.current_stock_name else self.current_stock_code
        self.transactions.append({
            'time': timestamp,
            'stock': stock_name,
            'action': action,
            'shares': shares,
            'price': price,
            'amount': amount,
            'profit': profit
        })
        # 更新底部状态栏
        self.status_label.text = f'[{timestamp[-8:]}] {action} {shares}股 @ {price:.2f}，金额 {amount:,.2f}'
        if profit != 0:
            self.status_label.text += f' 盈亏 {profit:+,.2f}'
    
    def show_transaction_history(self, instance):
        """弹窗显示完整交易记录"""
        if not self.transactions:
            show_popup('交易记录', '暂无交易记录', size_hint=(0.7, 0.3))
            return
        
        # 创建滚动内容
        content = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        
        # 标题行
        header = BoxLayout(size_hint_y=None, height=30, spacing=5)
        header.add_widget(Label(text='时间', size_hint_x=0.25, bold=True, font_size='11sp'))
        header.add_widget(Label(text='股票', size_hint_x=0.2, bold=True, font_size='11sp'))
        header.add_widget(Label(text='操作', size_hint_x=0.12, bold=True, font_size='11sp'))
        header.add_widget(Label(text='股数', size_hint_x=0.1, bold=True, font_size='11sp'))
        header.add_widget(Label(text='价格', size_hint_x=0.1, bold=True, font_size='11sp'))
        header.add_widget(Label(text='盈亏', size_hint_x=0.13, bold=True, font_size='11sp'))
        content.add_widget(header)
        
        # 分隔线
        sep = Label(text='─' * 40, size_hint_y=None, height=5, font_size='10sp')
        content.add_widget(sep)
        
        # 每条交易记录
        total_profit = 0.0
        for trans in self.transactions:
            row = BoxLayout(size_hint_y=None, height=28, spacing=5)
            row.add_widget(Label(text=trans['time'][5:16], size_hint_x=0.25, font_size='10sp'))
            row.add_widget(Label(text=trans['stock'], size_hint_x=0.2, font_size='10sp'))
            row.add_widget(Label(text=trans['action'], size_hint_x=0.12, font_size='10sp'))
            row.add_widget(Label(text=str(trans['shares']), size_hint_x=0.1, font_size='10sp'))
            row.add_widget(Label(text=f"{trans['price']:.2f}", size_hint_x=0.1, font_size='10sp'))
            
            profit_text = f"{trans['profit']:+,.2f}" if trans['profit'] != 0 else '--'
            profit_color = (0.3,0.9,0.3,1) if trans['profit'] > 0 else (0.9,0.3,0.3,1) if trans['profit'] < 0 else (0.7,0.7,0.7,1)
            profit_label = Label(text=profit_text, size_hint_x=0.13, font_size='10sp', color=profit_color)
            row.add_widget(profit_label)
            content.add_widget(row)
            
            total_profit += trans['profit']
        
        # 汇总信息
        sep2 = Label(text='─' * 40, size_hint_y=None, height=5, font_size='10sp')
        content.add_widget(sep2)
        
        summary = BoxLayout(size_hint_y=None, height=35, spacing=10, padding=[10,5])
        summary.add_widget(Label(text=f"总盈亏: {total_profit:+,.2f}", bold=True, 
                                  color=(0.3,0.9,0.3,1) if total_profit >= 0 else (0.9,0.3,0.3,1)))
        summary.add_widget(Label(text=f"当前总资产: {self.cash + (self.position * (self.kline_data[self.current_index]['close'] if self.kline_data else 0)):,.2f}", 
                                  font_size='11sp'))
        content.add_widget(summary)
        
        # 放入滚动视图
        scroll = ScrollView(size_hint=(1, 0.9))
        scroll.add_widget(content)
        
        popup_root = BoxLayout(orientation='vertical', size_hint=(1, 0.7), spacing=5)
        popup_root.add_widget(scroll)
        
        # 底部操作按钮
        action_row = BoxLayout(size_hint_y=0.1, spacing=8)
        clear_btn = Button(text='清空记录', background_color=(0.5,0.3,0.3,1))
        close_btn = Button(text='关闭', background_color=(0.3,0.3,0.3,1))
        action_row.add_widget(clear_btn)
        action_row.add_widget(close_btn)
        popup_root.add_widget(action_row)
        
        popup = Popup(title='交易记录', content=popup_root, size_hint=(0.95, 0.85))
        
        def clear_history(instance):
            self.transactions.clear()
            popup.dismiss()
            show_popup('提示', '交易记录已清空', size_hint=(0.6,0.25))
        
        clear_btn.bind(on_press=clear_history)
        close_btn.bind(on_press=lambda instance: popup.dismiss())
        apply_chinese_font(popup_root)
        popup.open()
    
    def show_loading(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        title_label = Label(text='数据加载中', font_size='15sp', bold=True)
        msg1 = Label(text='正在从 baostock 获取数据...', font_size='14sp')
        msg2 = Label(text='首次加载可能稍慢', font_size='12sp', color=(0.7,0.7,0.7,1))
        content.add_widget(title_label)
        content.add_widget(msg1)
        content.add_widget(msg2)
        apply_chinese_font(content)
        self.loading_popup = Popup(title='', separator_height=0, content=content, size_hint=(0.7,0.3), auto_dismiss=False)
        self.loading_popup.open()
    
    def hide_loading(self):
        if self.loading_popup:
            self.loading_popup.dismiss()
            self.loading_popup = None

    def _start_data_loading(self):
        self.show_loading()
        threading.Thread(target=self._load_stock_data_worker, daemon=True).start()

    def _load_stock_data_worker(self):
        result = {'error': None}
        try:
            if self.app.selected_mode == 'random':
                code, name = get_random_non_st_stock()
                if code is None:
                    result['error'] = '无法获取股票池，请检查网络或稍后重试'
                else:
                    result['current_stock_code'] = code
                    result['current_stock_name'] = name
            else:
                result['current_stock_code'] = self.app.stock_code
                result['current_stock_name'] = self.app.stock_name or f'{self.app.stock_code}'

            if not result['error']:
                start_str = self.app.start_date.strftime("%Y-%m-%d")
                end_str = self.app.end_date.strftime("%Y-%m-%d")
                data, err = fetch_stock_data_from_baostock(result['current_stock_code'], start_str, end_str)
                if err:
                    result['error'] = f'{err}\n请换一只股票或调整日期范围'
                else:
                    result['kline_data'] = data
                    if not result['kline_data']:
                        result['error'] = '该日期范围内无交易数据，请调整范围'
        except Exception as exc:
            result['error'] = f'数据加载失败: {exc}'

        Clock.schedule_once(lambda dt, payload=result: self._finish_data_loading(payload), 0)

    def _finish_data_loading(self, result):
        self.hide_loading()
        if result.get('error'):
            title = '数据错误' if ('网络' in result['error'] or '查询失败' in result['error']) else '错误'
            show_popup(title, result['error'])
            return

        self.current_stock_code = result.get('current_stock_code')
        self.current_stock_name = result.get('current_stock_name')
        self.stock_name_label.text = self.current_stock_name
        self.stock_code_label.text = self.current_stock_code
        self.kline_data = result.get('kline_data', [])

        calculate_macd_series(self.kline_data)
        self.cash = self.initial_capital
        self.position = 0
        self.avg_cost = 0.0
        self.current_index = 0
        self.transactions.clear()

        self.update_kline()
        self.update_account_info()
    
    def load_stock_data(self, dt=None):
        self._start_data_loading()
    
    def random_stock(self, instance):
        if self.app.selected_mode != 'random':
            show_popup('提示', '仅随机模式支持换股')
            return
        self.cash = self.initial_capital
        self.position = 0
        self.avg_cost = 0.0
        self.transactions.clear()
        self._start_data_loading()

    def go_back_to_start(self, instance):
        self.app.show_start_screen()
    
    def update_kline(self):
        if not self.kline_data:
            return
        self.kcanvas.set_data(self.kline_data, self.current_index)
        self.volume_canvas.set_data(self.kline_data, self.current_index)
        self.macd_canvas.set_data(self.kline_data, self.current_index)
        cur = self.kline_data[self.current_index]
        prev_close = self.kline_data[self.current_index-1]['close'] if self.current_index > 0 else cur['open']
        change = ((cur['close'] - prev_close) / prev_close * 100) if prev_close else 0
        self.date_label.text = cur['date'].strftime('%Y-%m-%d')
        self.price_label.text = f'{cur["close"]:.2f}'
        self.change_label.text = f'{change:+.2f}%'
        self.high_label.text = f'{cur["high"]:.2f}'
        self.low_label.text = f'{cur["low"]:.2f}'
        self.open_label.text = f'{cur["open"]:.2f}'
        self.turnover_label.text = f'{cur.get("turnover",0):.2f}%'
    
    def update_account_info(self):
        if not self.kline_data:
            return
        price = self.kline_data[self.current_index]['close']
        market = self.position * price
        total = self.cash + market
        profit = market - self.position * self.avg_cost if self.position else 0
        total_profit = total - self.initial_capital
        line1 = f'现金 {self.cash:,.0f}   持仓 {self.position}股'
        line2 = f'总资产 {total:,.0f}   浮盈 {profit:+,.0f}   总盈亏 {total_profit:+,.0f}'
        self.status_label.text = f"{line1}\n{line2}"
    
    def max_buy(self):
        if not self.kline_data:
            return 0
        price = self.kline_data[self.current_index]['close']
        return int(self.cash // price) if price > 0 else 0
    
    def open_trade_popup(self, action):
        if not self.kline_data:
            return
        price = self.kline_data[self.current_index]['close']
        if action == 'buy':
            max_shares = self.max_buy()
            title, subtitle, confirm_text = '买入', f'价格{price:.2f} 最多买{max_shares}股', '确认买入'
        else:
            max_shares = self.position
            title, subtitle, confirm_text = '卖出', f'价格{price:.2f} 最多卖{max_shares}股', '确认卖出'
        if max_shares <= 0:
            show_popup('提示', '无资金或持仓')
            return
        
        popup_root = BoxLayout(orientation='vertical', padding=12, spacing=10)
        info = Label(text=subtitle, size_hint_y=0.22, font_size='12sp')
        share_input = TextInput(text=str(max(1,max_shares//2)), input_filter='int', size_hint_y=0.18)
        ratio_row = BoxLayout(size_hint_y=0.22, spacing=6)
        for label, ratio in [('1/4',0.25),('1/3',1/3),('1/2',0.5),('全仓',1.0)]:
            btn = Button(text=label)
            btn.bind(on_press=lambda instance, r=ratio: setattr(share_input, 'text', str(max(1,int(max_shares*r)))))
            ratio_row.add_widget(btn)
        action_row = BoxLayout(size_hint_y=0.22, spacing=8)
        confirm = Button(text=confirm_text, background_color=(0.2,0.65,0.3,1))
        cancel = Button(text='取消')
        action_row.add_widget(confirm)
        action_row.add_widget(cancel)
        popup_root.add_widget(Label(text=title, size_hint_y=0.16, bold=True))
        popup_root.add_widget(info)
        popup_root.add_widget(share_input)
        popup_root.add_widget(ratio_row)
        popup_root.add_widget(action_row)
        popup = Popup(title=title, content=popup_root, size_hint=(0.9,0.52))
        
        def do_trade(instance):
            try:
                shares = int(share_input.text)
            except:
                show_popup('错误', '无效数字')
                return
            if shares <= 0 or shares > max_shares:
                show_popup('错误', '股数超限')
                return
            if action == 'buy':
                cost = shares * price
                if cost > self.cash:
                    show_popup('资金不足', f'需要{cost:.2f}')
                    return
                self.position += shares
                self.cash -= cost
                self.avg_cost = (self.avg_cost * (self.position - shares) + cost) / self.position
                self.add_transaction('买入', shares, price, cost, 0.0)
            else:  # 卖出
                amount = shares * price
                # 估算这笔卖出的盈亏（平均成本法）
                estimated_cost = shares * self.avg_cost
                profit = amount - estimated_cost
                self.cash += amount
                self.position -= shares
                if self.position == 0:
                    self.avg_cost = 0
                self.add_transaction('卖出', shares, price, amount, profit)
            self.update_account_info()
            popup.dismiss()
        confirm.bind(on_press=do_trade)
        cancel.bind(on_press=lambda instance: popup.dismiss())
        apply_chinese_font(popup_root)
        popup.open()
    
    def buy(self, instance): self.open_trade_popup('buy')
    def sell(self, instance): self.open_trade_popup('sell')
    
    def prev_day(self, instance):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_kline()
            self.update_account_info()
        else:
            show_popup('提示', '第一天')
    
    def next_day(self, instance):
        if self.current_index < len(self.kline_data)-1:
            self.current_index += 1
            self.update_kline()
            self.update_account_info()
        else:
            show_popup('提示', '最后一天')


# ========================== 字体中文支持 ==========================
from kivy.core.text import LabelBase
try:
    LabelBase.register(name='ChineseFont', fn_regular='C:/Windows/Fonts/msyh.ttc')
except:
    try:
        LabelBase.register(name='ChineseFont', fn_regular='/System/Library/Fonts/PingFang.ttc')
    except:
        try:
            LabelBase.register(name='ChineseFont', fn_regular='/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf')
        except:
            pass

def apply_chinese_font(widget):
    if hasattr(widget, 'font_name'):
        widget.font_name = 'ChineseFont'
    for child in getattr(widget, 'children', []):
        apply_chinese_font(child)


# ========================== 主应用 ==========================
class StockSimulatorApp(App):
    def build(self):
        self.selected_mode = 'random'
        self.start_date = None
        self.end_date = None
        self.stock_code = None
        self.stock_name = None
        # 使用竖直根布局并清除 padding/spacing，避免屏幕切换时产生多余空白
        self.root_layout = BoxLayout(orientation='vertical', padding=[0,0,0,0], spacing=0)
        self.start_screen = StartScreen(self)
        self.root_layout.add_widget(self.start_screen)
        return self.root_layout
    
    def show_main_screen(self):
        self.root_layout.clear_widgets()
        self.main_screen = MainScreen(self)
        self.root_layout.add_widget(self.main_screen)

    def show_start_screen(self):
        self.root_layout.clear_widgets()
        self.root_layout.add_widget(self.start_screen)


if __name__ == '__main__':
    StockSimulatorApp().run()