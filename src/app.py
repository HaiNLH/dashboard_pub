from dash import Dash, html, dcc, Input, Output, dash_table
import dash_bootstrap_components as dbc
from dash import dcc
import plotly.graph_objs as go
import pandas as pd
import numpy as np
import requests
import json
import time
# import datetime
import os
import math
from decimal import Decimal


app = Dash(external_stylesheets=[dbc.themes.CYBORG])
server = app.server
#reutrn dropdown options
def dropdown_options(title, options, defauilt_value, _id):
    return html.Div(children = [
        html.H2(title),
        dcc.Dropdown(options = options, value = defauilt_value, id = _id)
    ])

app.layout = html.Div(children = [ 
    html.Div(children = [
        dash_table.DataTable(id = "ft_close_table",page_size=20),
        ],
        style = {"width" : "300px",
                "padding-right": "50px",
                "flex-direction": "column",
                "align-items": "center",
                "justify-content": "center",}),
    html.Div(children = [
        dash_table.DataTable(id = "ft_open_table",page_size=20),
        ],
        style = {"width" : "300px",
                "padding-right": "50px",
                "flex-direction": "column",
                "align-items": "center",
                "justify-content": "center",}),
        
    html.Div(children = [ 
        dropdown_options("Quantity Precision", 
            options = ['0','1','2','3','4','5','6'], defauilt_value = 4, _id = 'quantity_precision'),
        dropdown_options("Size", 
        options = ['100','500','1000','5000','10000'], defauilt_value = 5000, _id = 'size'),

    ], style = {'padding-left' : '50px'}),
    

    dcc.Interval(id = "timer", interval = 3000),
])

def table_styling(df, side):
    if side == "sell":
        bar_color = "rgba(230, 31, 7, 0.2)"
        font_color = "rgb(230, 31, 7)"
    elif side =="buy":
        bar_color = "rgba(13, 230, 49, 0.2)"
        font_color = "rgb(13, 230, 49)"
    cell_bg_color = "#060606"

    styles = []
    styles.append({
        "if": {"column_id": "price"},
        "color": font_color,
    })
    return styles

#aggregate level
def aggregate_levels(levels_df, agg_level = Decimal('0.1'), side = 'buy'):
    #whether to conclude the right side of the bin
    if side == "buy":
        right  = False
        label_func = lambda x: x.left
    elif side == "sell":
        right = True
        label_func = lambda x: x.right
    # print(type(levels_df))
    min_level = math.floor(Decimal(min(levels_df.price))/agg_level - 1)*agg_level
    max_level = math.ceil(Decimal(max(levels_df.price))/agg_level + 1)*agg_level
    level_bounds = [float(min_level + agg_level*x) for x in range 
                    (int((max_level - min_level)/agg_level) + 1)]
    
    levels_df['bin'] = pd.cut(levels_df.price, bins = level_bounds, precision = 10, right = right)
    levels_df = levels_df.groupby('bin').agg(quantity = ('quantity', 'sum')).reset_index()
    #getting price
    levels_df['price'] = levels_df['bin'].apply(label_func)
    #filter & drop bin
    levels_df = levels_df[levels_df.quantity > 0]
    levels_df = levels_df[['price','quantity']]
    # print(levels_df)
    return levels_df

@app.callback(Output("ft_close_table", "data"),
                Output("ft_open_table", "data"),
                # Output("open-buy-graph", "figure"),
                # Output("buy_table", "style_data_conditional"),
                # Output("sell_table", "data"),
                # Output("sell_table", "style_data_conditional"),
                # Output("mid-price", "children"),
                # Output("number_of_buy_open_orders", "children"),
                # Output("number_of_sell_open_orders", "children"),

                # Input("quantity_precision", "value"),
                # Input("price_precision", "value"),
                # Input("aggregation_level", "value"),
                # Input("crypto_pair", "value"),
                Input("quantity_precision", "value"),
                Input("size", "value"),
                Input("timer", "n_intervals"))

# def update_ordebook(quantity_precision, price_precision, agg_level, symbol, n_intervals):
def update_ordebook(precision,size, n_intervals):
    
    url = "https://api.binance.com/api/v3/depth"
    url_orai = "http://34.138.227.225:3005/oraichain/future" 
    
    levels_to_show = 10

    params = {
        # "symbol" : symbol.upper(),
        "offset" : 0,
        "size" : size,
    }
    data = requests.get(url_orai, params = params).json()
    # Future
    data = pd.DataFrame(data)
    columns_to_divide = [
    'leverage', 'offerAmount', 'askAmount', 'marginAmount', 'entryPrice',
    'takeProfit', 'stopLoss', 'fee', 'pnl', 'fundingPayment', 'volume'
    ]

    data[columns_to_divide] /= 1000000
    # data[columns_to_divide] = data[columns_to_divide].round(precision)
    open_df = pd.DataFrame(data[data['status']=='Open'])
    df2 = open_df
    df2['stop_loss_pct'] = df2.apply(lambda x: ((x['stopLoss'] / x['entryPrice'] - 1) * x['leverage']) if (
        x['direction'] == "Buy" and x['entryPrice'] != 0 and x['leverage'] != 0
    ) else (
        (1 - x['stopLoss'] / x['entryPrice']) * x['leverage']) if (
        x['entryPrice'] != 0 and x['leverage'] != 0
    ) else -1, axis=1)

    df2['take_profit_pct'] = df2.apply(lambda x: ((x['takeProfit'] / x['entryPrice'] - 1) * x['leverage']) if (
        x['direction'] == "Buy" and x['entryPrice'] != 0 and x['leverage'] != 0
    ) else (
        (1 - x['takeProfit'] / x['entryPrice']) * x['leverage']) if (
        x['entryPrice'] != 0 and x['leverage'] != 0
    ) else -1, axis=1)
    df2['take_profit_take'] = df2['marginAmount'] * df2['take_profit_pct']
    df2['stop_loss_give'] = df2['marginAmount'] * df2['stop_loss_pct']
    final_open = df2.groupby(['bidderAddr', 'direction']).agg({'orderId': 'count','marginAmount': 'sum', 'volume': 'sum', 'take_profit_take':'sum','stop_loss_give':'sum','fee':'sum'}).reset_index()
    format_open = ['marginAmount', 'volume', 'take_profit_take', 'stop_loss_give', 'fee']
    final_open[format_open] = final_open[format_open].applymap(lambda x: f"{x:.{precision}f}")
    # print(final_open)

    close_df = pd.DataFrame(data[data['status'] !='Open'])
    df1 = close_df
    # print(df1)
    df1['volume'] = df1['leverage'] * df1['marginAmount']
    df1['closePrice'] =df1['offerAmount']/df1['askAmount']
    df1['closePct'] = df1.apply(lambda x: 
                                ((x['closePrice'] / x['entryPrice'] - 1) * x['leverage'])
                                if x['direction'] == 'Buy' and x['entryPrice'] != 0
                                else
                                ((1 - x['closePrice'] / x['entryPrice']) * x['leverage'])
                                if x['direction'] == 'Sell' and x['entryPrice'] != 0
                                else 0, axis=1)
    df1['loseAmount'] =df1.apply(lambda x:(x['closePct']*x['marginAmount']) if x['closePct'] <0 else 0, axis = 1)
    df1['winAmount'] = df1.apply(lambda x: (x['closePct']*x['marginAmount']) if x['closePct'] >=0 else 0, axis = 1)
    final_close = df1.groupby(['bidderAddr', 'direction']).agg({'orderId': 'count','marginAmount': 'sum', 'volume': 'sum', 'loseAmount':'sum','winAmount':'sum','fee':'sum','fundingPayment':'sum'}).reset_index()
    format = ['marginAmount', 'volume', 'loseAmount', 'winAmount', 'fee', 'fundingPayment']
    final_close[format] = final_close[format].applymap(lambda x: f"{x:.{precision}f}")
    
    
    
    return (final_close.to_dict("records"), final_open.to_dict("records"),
            # {'data': [graph],'layout' : go.Layout(title='Open Order',yaxis = dict(range=[0, max(buy_offer, sell_offer)]))},'#_buy_open_orders: ' + str(number_of_buy_open_orders),'#_sell_open_orders: ' + str(number_of_sell_open_orders)
    )
    pass

if __name__ == '__main__':
    app.run_server(debug=True)
