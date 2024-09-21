from dash import Dash, html, dash_table, dcc,html,ctx,callback_context
from dash.dependencies import Output, Input, State
import dash_bootstrap_components as dbc
import dash_daq as daq
import dash_ag_grid as dag
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import base64
import io
from flask import send_file
import uuid
import openpyxl
#фласк движения, убрать 
from flask import Flask, send_from_directory
import os
from flask_caching import Cache
import pickle
import shutil
from scipy.optimize import minimize_scalar
from functools import partial
from plotly.subplots import make_subplots
import json
#-------------------------------------------------------------------------------------------------------------------------------------

#external_scripts = ["https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/2.0.6/clipboard.min.js"] #для копироания данных, external_scripts=external_scripts
#----------------------------------------------------------------Служебка---------------------------------------------------------------------
server = Flask(__name__) #это для фласк суеты
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP],suppress_callback_exceptions=True,server = server) #Initialize the app+тема BOOTSTRAP
# suppress_callback_exceptions=True от пустых значений
#server = app.server №это для деплоя

# Настройка кэша для хранения загруженных данных
cache = Cache(app.server, config={'CACHE_TYPE': 'filesystem','CACHE_DIR': 'cache-directory'})

# Директория для сохранения загруженных файлов, если не сущ, то создается
UPLOAD_DIRECTORY = "app_uploaded_files"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

columns_not_light=['Начальное пластовое давление' #колонки не исп. в формате ligth
                   'Градиент начального давления закрытия, атм/м',
                   'Градиент горизонтального напряжения, атм/м'
                   'Средний динамический коэффициент Пуассона для песчаника',
                   'Средний динамический коэффициент Пуассона для алевролита/аргиллита',
                   'Средний динамический модуль Юнга для песчаника',
                   'Средний динамический модуль Юнга для алевролита/аргиллита',
                   'Расстояние между рядами скважин']

#1)Сохраняет загруженный файл на сервере (комп)
def save_file(name, content):
    content_type, content_string = content.split(',')
    decoded = base64.b64decode(content_string)
    if 'xlsx' in name:
        df = pd.read_excel(io.BytesIO(decoded))
    elif 'csv' in name:
        df = pd.read_csv(io.StringIO(decoded.decode('cp1251')), sep=";")
    elif 'pickle' in name or 'pkl' in name:
        df = pd.read_pickle(io.BytesIO(decoded))
    else:
        return 'Ошибка: неизвестный формат'
    df['Скважина'] = df['Скважина'].astype(str)
    df['Обв, %']=(df['Жидкость, тыс т']-df['Нефть, тыс т']) / df['Жидкость, тыс т']*100 
    df['Межпортовое расстояние']=df['Длина горизонтального ствола'] / (df['Число стадий']+1)
    df['Накопленная нефть, тыс т']=df.groupby(['Месторождение','Скважина'])['Нефть, тыс т'].cumsum()
    df['Накопленная жидкость, тыс т']=df.groupby(['Месторождение','Скважина'])['Жидкость, тыс т'].cumsum()
    try:
        df['Накопленная жидкость, тыс м3']=df.groupby(['Месторождение','Скважина'])['Жидкость, тыс м3'].cumsum()
    except:
        print('попытка не пытка')
    df['1/Вязкость']=1/df['Средняя вязкость флюида в пластовых условиях']
    if 'ПНГ, млн м3' in df.columns: #проверка на ии или факт/гдм данные
        df['ГФ, м3/т']=df['ПНГ, млн м3'] / df['Нефть, тыс т']*1000 
        df['Накопленный ПНГ, млн м3']=df.groupby(['Месторождение','Скважина'])['ПНГ, млн м3'].cumsum()
 
    with open(os.path.join(UPLOAD_DIRECTORY, name.split('.')[0]+'_full.pickle'), 'wb') as f:      #full format
        pickle.dump(df, f)
    with open(os.path.join(UPLOAD_DIRECTORY, name.split('.')[0]+'_lite.pickle'), 'wb') as f: #lite format
        pickle.dump(df.drop(columns=[col for col in columns_not_light if col in df.columns ]), f) #удаление колонок для формата лайт из тех которые есть в df

#2)Читает файл с сервера(папка скачивания) и возвращает DataFrame
def read_file(name,size):
    return pd.read_pickle(os.path.join(UPLOAD_DIRECTORY, name.split('.')[0]+
                                       {'lite':'_lite.pickle',
                                        'full':'_full.pickle',
                                        'lite-filter':'_lite-filter.pickle',
                                        'mvr':'_mvr.pickle'}[size])) #выбор префикса к названию в заисимости от size и типа для mvr
#----------------------------------------------------------------VIDGETS---------------------------------------------------------------------
#Выпадающие списки--------------------------------------------------
cluster_selector = dcc.Dropdown(
    id='cluster-selector',
    options=[
        {'label': str(cluster), 'value': cluster} for cluster in [3, 6, 7, 8]],
    multi=True,
    clearable=False)  # Запретить очистку выбора)

field_selector = dcc.Dropdown(
    id='field-selector',
    multi=True,
    clearable=False)# Запретить очистку выбора

plast_selector = dcc.Dropdown(
    id='plast-selector',
    multi=True,
    clearable=False) # Запретить очистку выбора

profil_selector=dcc.Dropdown(
    id='profil-selector',
    options=[
             {'label': html.Span(['Qн, т/сут (МЭР)'], style={'color': 'Brown', 'font-size': 15}), 'value': 'Qн, т/сут (МЭР)'},
             {'label': html.Span(['Qн, т/сут (ТР)'], style={'color': 'Brown', 'font-size': 15}), 'value': 'Qн, т/сут (МЭР)'},
             {'label': html.Span(['Темп падения Qн, д.ед'], style={'color': 'Brown', 'font-size': 15}), 'value': 'Темп падения Qн'},
             {'label': html.Span(['Нефть, тыс. т'], style={'color': 'Brown', 'font-size': 20}), 'value': 'Нефть, тыс т'},
             {'label': html.Span(['Накопленная нефть, тыс. т'], style={'color': 'Brown', 'font-size': 23}), 'value': 'Накопленная нефть, тыс т'},
             {'label': html.Span(['Qж, м3/сут (МЭР)'], style={'color': 'Green', 'font-size': 15}), 'value': 'Qж, м3/сут  (МЭР)'},
             {'label': html.Span(['Qж, м3/сут (ТР)'], style={'color': 'Green', 'font-size': 15}), 'value': 'Qж, м3/сут (ТР)'},
             {'label': html.Span(['Qж, т/сут (МЭР)'], style={'color': 'Green', 'font-size': 15}), 'value': 'Qж, т/сут  (МЭР)'},
             {'label': html.Span(['Qж, т/сут (ТР)'], style={'color': 'Green', 'font-size': 15}), 'value': 'Qж, т/сут (ТР)'},                  
             {'label': html.Span(['Темп падения Qж, д.ед'], style={'color': 'Green', 'font-size': 15}), 'value': 'Темп падения Qж'},
             {'label': html.Span(['Жидкость, тыс. м3'], style={'color': 'Green', 'font-size': 20}), 'value': 'Жидкость, тыс т'},
             {'label': html.Span(['Жидкость, тыс. т'], style={'color': 'Green', 'font-size': 20}), 'value': 'Жидкость, тыс т'},
             {'label': html.Span(['Накопленная жидкость, тыс. т'], style={'color': 'Green', 'font-size': 23}), 'value':'Накопленная жидкость, тыс т'},
             {'label': html.Span(['Qг, тыс.м3/сут'], style={'color': 'Gold', 'font-size': 15}), 'value': 'Qг, тыс.м3/сут'},
             {'label': html.Span(['ПНГ, млн. м3'], style={'color': 'Gold', 'font-size': 20}), 'value': 'ПНГ, млн м3'},
             {'label': html.Span(['Накопленный ПНГ, млн. м3'], style={'color': 'Gold', 'font-size': 23}), 'value': 'Накопленный ПНГ, млн м3'},
             {'label': html.Span(['ГФ, м3/т'], style={'color': 'Grey', 'font-size': 15}), 'value': 'ГФ, м3/т'},
             {'label': html.Span(['Обводненность, %'], style={'color': 'blue', 'font-size': 15}), 'value': 'Обв, %'}],
        value='Нефть, тыс т', clearable=False,multi=False)
#-------------------------------------------------------------------------СЛАЙДЕРЫ ЗАКАНЧИВАНИЯ/ГРП------------------------------------------------------------------
#слайдер для фильтра Lгс
lgs_slider=dcc.RangeSlider(step=50,marks=None,tooltip={"placement": "top", "always_visible": True},id='lgs-slider')
#слайдер для фильтра числа стадий
nfrac_slider=dcc.RangeSlider(step=1,marks=None,tooltip={"placement": "top", "always_visible": True},id='nfrac-slider')
#слайдер для фильтра тоннажа
mprop_slider=dcc.RangeSlider(step=10,marks=None,tooltip={"placement": "top", "always_visible": True},id='mprop-slider')
#----------------------------------------------------------------------------------ГФХ---------------------------------------------------------------------------
perm_slider=dcc.RangeSlider(marks=None,step=0.01,tooltip={"placement": "top", "always_visible": True},id='perm-slider')
hef_slider=dcc.RangeSlider(marks=None,tooltip={"placement": "top", "always_visible": True},id='hef-slider')
hoil_slider=dcc.RangeSlider(marks=None,tooltip={"placement": "top", "always_visible": True},id='hoil-slider')
soil_slider=dcc.RangeSlider(marks=None,tooltip={"placement": "top", "always_visible": True},id='soil-slider')
#----------------------------------------------------------------------------------PVT---------------------------------------------------------------------------
rs_slider=dcc.RangeSlider(marks=None,tooltip={"placement": "top", "always_visible": True},id='rs-slider')
mu_slider=dcc.RangeSlider(marks=None,tooltip={"placement": "top", "always_visible": True},id='mu-slider')
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------
deviat_slider=dcc.Slider(id='deviat-slider',min=0,max=100,step=5,value=10,marks=None,tooltip={"placement": "top", "always_visible": True,"template": "{value}%"})

label_dict={'Qн, т/сут (МЭР)':['Дебит нефти (МЭР)','т/сут'],
            'Qн, т/сут (ТР)':['Дебит нефти (ТР)','т/сут'],
            'Темп падения Qн':['Темп падения Qн','д.ед'],
            'Нефть, тыс т':['Добыча нефти','тыс. т'],
            'Накопленная нефть, тыс т':['Накопленная нефть', 'тыс. т'],
            'Qж, м3/сут (МЭР)':['Дебит жидкости (МЭР)','м3/сут'],
            'Qж, т/сут (МЭР)':['Дебит жидкости (МЭР)','т/сут'],
            'Qж, м3/сут (ТР)':['Дебит жидкости (ТР)','м3/сут'],
            'Qж, т/сут (ТР)':['Дебит жидкости (ТР)','т/сут'],
            'Темп падения Qж':['Темп падения Qж','д.ед'],
            'Жидкость, тыс т':['Добыча жидкости','тыс. т'],
            'Жидкость, тыс м3':['Добыча жидкости','тыс. м3'],
            'Накопленная жидкость, тыс т':['Накопленная жидкость', 'тыс. т'],
            'Накопленная жидкость, тыс м3':['Накопленная жидкость', 'тыс. м3'],
            'Qг, тыс.м3/сут':['Дебит газа','тыс.м3/сут'],
            'ПНГ, млн м3':['Добыча ПНГ','млн м3'],
            'Накопленный ПНГ, млн м3':['Накопленный ПНГ', 'млн м3'],
            'ГФ, м3/т':['Газовый фактор','м3/т'],
            'Обв, %':['Обводненность','%']}

variable_selector=dcc.Dropdown(
    id='variable-selector',
    options=['Средняя проницаемость (ГИС)', 'Средняя эффективная мощность коллектора (ГИС)','Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)','Вязкость', # гфх
             'Длина горизонтального ствола','Число стадий','Межпортовое расстояние','Масса проппанта на стадию','Тип ГРП'], #заканчивание
    value='Число стадий',
    multi=False,
    clearable=False)
#------------------------------------------------------------------
#для загрузки прогноза ИИ
cluster_selector_ai = dcc.Dropdown(
    id='cluster-selector-ai',
    options=[
        {'label': str(cluster), 'value': cluster} for cluster in [3, 6, 7, 8]],
    multi=True,
    clearable=False)  # Запретить очистку выбора)

field_selector_ai = dcc.Dropdown(
    id='field-selector-ai',
    multi=True,
    clearable=False)

plast_selector_ai = dcc.Dropdown(
    id='plast-selector-ai',
    multi=True,
    clearable=False)

#---------------------------------------------------------ЗАГРУЗЧИК ДАННЫХ ФАКТ И ПРОГНОЗ ИИ-------------------------------------------------------------------------------------
fact_upload=dcc.Upload(id='upload fact data',
                children=html.Div(['Добавить файл с', html.B(' фактом/ГДМ')]),
                style={'width': '80%',
                       'height': '75px',
                       'lineHeight': '60px',
                       'borderWidth': '2px',
                       'borderStyle': 'dashed',
                       'borderRadius': '15px',
                       'textAlign': 'center',
                       'align':'left',
                       'margin': '10px'})

ai_upload=dcc.Upload(id='upload ai data',
            children=html.Div(['Добавить файл с', html.B(' прогнозом ГДМ/ИИ')]),
            style={'width': '80%',
                   'height': '75px',
                   'lineHeight': '60px',
                   'borderWidth': '2px',
                   'borderStyle': 'dashed',
                   'borderRadius': '15px',
                   'textAlign': 'center',
                   'white-space': 'normal',
                   'word-wrap': 'break-word',
                   'overflow': 'hidden',
                   'align':'left',
                   'margin': '10px'})

mvr_upload=dcc.Upload(id='upload mvr data',
            children=html.Div(['Добавить файл с', html.B(' расчётами МВР')]),
            style={'width': '80%',
                   'height': '75px',
                   'lineHeight': '60px',
                   'borderWidth': '2px',
                   'borderStyle': 'dashed',
                   'borderRadius': '15px',
                   'textAlign': 'center',
                   'white-space': 'normal',
                   'word-wrap': 'break-word',
                   'overflow': 'hidden',
                   'align':'left',
                   'margin': '10px'})
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------
#ТАБЫ--------------(Здесь задается контент по табам)---------------------------------------------
#верификация профилей
tab1_content=[
    dbc.Row([
        html.Hr(),
        dbc.Col(html.Div(html.H6('Выбор отклонения, %:')),width={'size':2,'offset':0}), #,style={'width':'100px'}  ,width={'size':4,'offset':0}
        dbc.Col(daq.ToggleSwitch(id='deviat-check',value=False,label='Off/On',labelPosition='bottom'),width={'size':2,'offset':1}),  
        ]),
    dbc.Row([
        html.Div(deviat_slider, style={'width':'520px','margin-top':'8px','margin-bottom':'0px'}),
        html.Div(id='deviat-sample-output'), #вывод количества отфильтрованных расчетов по отклонению
        html.Hr()
    ]),
    dbc.Button("Показать функционал подбора профилей",id="collapse-button-3",className="mb-3",n_clicks=0),
    dbc.Collapse([
        dbc.Row([
            html.H6('Выбор профиля для подбора:'), #подбор персентиля под профиль
            html.Div(dcc.Dropdown(
                    id='profil-choise',
                    options=[{'label': f'{i}', 'value': i} for i in ['P10','Среднее','P50','P90']],
                    value=['P50'], multi=True, clearable=False),style={'width':'400px','margin-bottom':'10px'}),
            dcc.Loading(type="default",children=[html.Div(id='tables-percentile')]) #вывод таблицы
        ])
    ],is_open=False,id='collapse-3'),
    dbc.Row([
        html.H4('Выбранный профиль – гистограмма добычи для выбранного шага'),
        html.Hr(),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='qstart histogram')]),
                 html.Div(dcc.Slider(1,12,1,id='step-slider',value=1))],style={'width':'100px'}),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='udeln qstart histogram')])],style={'width':'100px'}),
        dbc.Row() #слайдер годы
    ]),
    dbc.Row([
        html.Hr(),
        dbc.Col([html.H6('Выберите способ отображения фактических и прогнозных профилей'),]),
        dcc.RadioItems(['Веер профилей','Ящик с усами','По кластерам','По месторождениям','По пластам'],'Ящик с усами',
                       style={'display': 'flex', 'flexDirection': 'row', 'gap': '20px'},id='profil-rb'),
        html.Hr(),
        html.H4('Динамика профилей'),
        html.Hr(),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='profils')])],style={'width':'100px'}),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='udeln profils')])],style={'width':'100px'})
            ]),
    dbc.Row([
        html.H4('Динамика дисконтированных профилей'),
        html.Hr(),
        html.Div(dcc.Input(id="coef discont", type="number", value=14,placeholder="Ввод ставки дисконтирования,%",style={'width':'300px','margin-bottom':'20px'})),
        html.Hr(),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='discont profils')])],style={'width':'100px'}),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='udeln discont profils')])],style={'width':'100px'}),
            ]),
    dbc.Row([
        dbc.Col([
            dbc.Button('Экспорт профилей в Excel ⏬', id='profil-export-button',className="mb-3", n_clicks=0, style={'width': '300px'}),
            dcc.Download(id='profil-table-download'),
            dcc.Store(id='profil-table-download-store', data=False)],
            width=12, style={'display': 'flex', 'justify-content': 'center'}),
        #dbc.Modal([
        #    dbc.ModalHeader(dbc.ModalTitle('Экспорт завершен!')),
        #    dbc.ModalBody('Файл "Профиля отчет.xlsx" успешно сохранён')],
        #        id="modal-profil",
        #        size="sm",
        #        is_open=False,
        #        backdrop="static")  # Предотвращает закрытие модального окна при клике вне его
            ]),
    dbc.Button("Показать таблицы сравнения профилей",id="collapse-button-2",className="mb-3",n_clicks=0),
    dbc.Collapse(
        dbc.Row([
            html.H4('Таблица сравнения профилей', style={'width':'700px'}), #,'margin-top':'25px'
            html.Hr(),
            dbc.Col([
                html.Div(dcc.Dropdown(
                    id='num-criteria-tables',
                    options=[{'label': f'Таблица {i}', 'value': i} for i in ['P10','P50','P90']],
                    value=['P50'], multi=True, clearable=False),style={'margin-bottom':'10px'}),                
                dcc.Loading(type="default",children=[html.Div(id='criteria-tables')]) #вывод таблицы
                ],width={'size':5,'offset':0}), 
            dbc.Col([
                dcc.Markdown('$E_i = \\left| \\frac{Q_{\\text{факт}i} - Q_{\\text{ИИ}i}}{Q_{\\text{факт}i}} \\right|$ – относительная ошибка за 𝑖-ый год, %',id='ei',style={'font-size':'20px'}, mathjax=True),
                    dbc.Popover('Определение относительной ошибки',target="ei",body=True,placement='top-end',trigger="hover"),          
                dcc.Markdown('Критерий 1: $\\frac{1}{10} \\sum_{i=1}^{10} E_i \\leq 10$%',id='crit1',style={'font-size':'20px'}, mathjax=True),
                    dbc.Popover('Средняя Ei для жидкости/нефти за 3 года не должна превышать 10%',target="crit1",body=True,placement='top-end',trigger="hover"),
                dcc.Markdown('Критерий 2: $E_i\\leq 10$% для каждого i=1,2,3',id='crit2',style={'font-size':'20px'}, mathjax=True),
                    dbc.Popover('Ei для жидкости/нефти за первые 3 года не должна превышать 10%',target="crit2",body=True,placement='top-end',trigger="hover"),          
                dcc.Markdown('Критерий 3: $\\left| \\frac{Q_{\\text{факт}}^{\\text{накоп }10} - Q_{\\text{ИИ}}^{\\text{накоп }10}}{Q_{\\text{факт}}^{\\text{накоп }10}} \\right| \\leq 10$%',
                            id='crit3',style={'font-size':'20px'}, mathjax=True),
                    dbc.Popover('Относительная разница накопленной добычи жидкости/нефти не должна превышать 10%',target="crit3",body=True,placement='top-end',trigger="hover"),          
                dcc.Markdown('Критерий 4: $\\left| \\frac{Q_{\\text{диск. факт}}^{\\text{накоп }10} - Q_{\\text{диск. ИИ}}^{\\text{накоп }10}}{Q_{\\text{диск. факт}}^{\\text{накоп }10}} \\right| \\leq 10$%', 
                            id='crit4',style={'font-size':'20px'},mathjax=True),
                    dbc.Popover('Относительная разница накопленной дисконтированной добычи жидкости/нефти не должна превышать 10%',target="crit4",body=True,placement='top-end',trigger="hover")
            ],width={'size':5,'offset':1}),
            html.Hr(style={'margin-top':'17px'}),
            dbc.Row([
                dcc.Loading(type="default",children=[dcc.Graph(id='ei histogram')])
                    ]) 
                ]),is_open=False,id='collapse-2'
                )
]

#Аналитика по факту
tab2_content=[
    dbc.Row([
        html.H6('Выбор параметра:'),
        html.Div(variable_selector, style={'width':'500px','margin-bottom':'40px'})]),
    dbc.Row([
        html.H4('Выбранный параметр – гистограмма по заканчиванию, ГФХ'),
        html.Hr(),
        dbc.Col([html.H6('Группировать по:'),dcc.RadioItems([{'label': 'По кластерам', 'value': 'Кластер'},
                                                             {'label': 'По месторождения', 'value': 'Месторождение'},
                                                             {'label': 'По пластам', 'value': 'Пласт'},
                                                             {'label': 'По скважинам', 'value': 'Скважина'}], 'Пласт',id='rb_hist_tab2')]),
        dbc.Col([html.H6('Выбрать ось х:'),dcc.RadioItems(['Ось х-значения','Ось х-объекты'],'Ось х-объекты',id='rb2_hist_tab2')],width={'size':10,'offset':0}),
        html.Hr(),
        dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='wellcomp histogram tab2')])),
        html.Hr()]),
    dbc.Col([
        html.H4('Таблица с параметрами "средней" скважины:', style={'width':'700px','margin-top':'25px'}),
        html.Hr(),
        dcc.Store(id='mean-well-table-store'), #для хранения таблицы средней скв
        dcc.Dropdown(
            id='row-selector',
            options=[
                {'label': 'Показать часть таблицы', 'value': 'short'},
                {'label': 'Показать всю таблицу (+геомеханика)', 'value': 'full'}],
                value='short', clearable=False, style={'width':'370px','margin-bottom':'10px'}),  # Начальное значение
        dash_table.DataTable(id='mean-well-table',
            data=[], 
            columns=[],
            #style_table={'overflowX': 'auto'},
            style_cell={
                'minWidth': '50px', 'width': '300px', 'maxWidth': '350px',
                'overflow': 'hidden',
                'textOverflow': 'ellipsis',}),
        dbc.Button("Экспорт таблицы в Excel ⏬", id="mean-well-table-export", n_clicks=0, className="mr-2",style={'margin-bottom':'25px','margin-top':'10px'} ),
        dcc.Download(id='mean-well-table-download')],width={'size':4,'offset':0})] #для экспорта таблицы в ексель

#Аналитика МВР
tab3_content=[
    dbc.Row([
            dcc.Loading(id='mvr-loading',type="default",children=mvr_upload),
            dbc.Col(width={'size':4,'offset':0}),
            dbc.Col(width={'size':4,'offset':0}),
            html.Hr()
            ]),
    dbc.Button("Показать таблицу фильтров МВР",id="collapse-button-4",className="mb-3",n_clicks=0),        
    dbc.Collapse(dbc.Row([dag.AgGrid(id='mvr-table',
                        className='ag-theme-quartz',
                        dashGridOptions={'pagination': True},
                                         #'theme':'quartz'
                        columnDefs=[],
                        rowData=[],
                        defaultColDef={"flex": 1, "minWidth": 150,"maxWidth": 250,"resizable": True, "sortable": True, "filter": True},
                        columnSize="autoSize"),
            ]),is_open=False,id='collapse-4'),        
    dbc.Row([html.H4('Параметры добычи от Lгс'),
             html.Hr()]),
    dbc.Row([dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='nd1-lgs')])),
             dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='q1-lgs')]))]),
            
    dbc.Row([dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='nd10-lgs')])),
             dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='q13-lgs')]))]),         
    dbc.Row([html.H4('Параметры добычи от Массы проппанта'),
             html.Hr()]),   
    dbc.Row([dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='nd1-mprop')])),
             dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='q1-mprop')]))]),
    dbc.Row([dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='nd10-mprop')])),
             dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='q13-mprop')]))]),
    dbc.Row([html.H4('Параметры добычи от Числа стадий'),
             html.Hr()]),   
    dbc.Row([dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='nd1-nfrac')])),
             dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='q1-nfrac')]))]),
    dbc.Row([dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='nd10-nfrac')])),
             dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='q13-nfrac')]))]),         
            ]        
#------------------------------------------------------------------------------------------------
#--------------------------------------------------------------layout-----------------------------------------------------------------------
app.layout = html.Div([
    html.H2(["Модуль для аналитики – ",
            html.Span(html.Em("ПроСкан"), style={'color': 'lightgray','text-shadow': '0.75px 0.75px 0 black, -0.75px -0.75px 0 black, -0.75px 0.75px 0 black, 0.75px -0.75px 0 black'})]),
    
    #html.H2(["Модуль для аналитики – ", html.Em("ProScan")]), 
    dbc.Row([
        dbc.Col([dcc.Loading(id='fact-loading',type="default",children=fact_upload)]),   
        dbc.Col(dbc.Button('Удалить кэш', id='cash button', outline=True, color='warning', className='me-1'), style={'width':'100px','margin-top':'30px'}),
        dbc.Col([dcc.Loading(id='ai-loading',type="default",children=ai_upload)]),     
        html.Hr(),
            ]),
    dbc.Row([
        dbc.Col([
            html.H6('Фильтр кластера:'),
            html.Div(cluster_selector, style={'width':'400px','margin-bottom':'10px'})]),
        dbc.Col(dbc.Button('Выбрать все',id='All cluster',color="info",n_clicks=0,className='me-1'),align='center'),  #кнопка cluster,style={'margin-bottom':'15px'}
        dbc.Col([
            html.H6('Фильтр кластера для ИИ:'),
            html.Div(cluster_selector_ai, style={'width':'400px','margin-bottom':'20px'})],align='center'),
        html.Hr()
    ]),
    dbc.Row([
        dbc.Col([    
            html.H6('Фильтр месторождения:'),
            dcc.Loading(type="default",children=[html.Div(field_selector, style={'width':'400px','margin-bottom':'10px'})])
            ]), #,width={'size':4,'offset':0}
        dbc.Col(dbc.Button('Выбрать все',id='All field',color="info",n_clicks=0,className='me-1'),align='center'), #кнопка field,style={'margin-bottom':'15px'}
        dbc.Col([
            html.H6('Фильтр месторождения для ИИ:'),
            dcc.Loading(type="default",children=[html.Div(field_selector_ai, style={'width':'400px','margin-bottom':'20px'})])],align='center'), #4 2 
        html.Hr()
    ]),
    dbc.Row([
        dbc.Col([
            html.H6('Фильтр пластов:'),
            dcc.Loading(type="default",children=[html.Div(plast_selector, style={'width':'400px','margin-bottom':'10px'})])       #,width={'size':4,'offset':0}
            ]), 
        dbc.Col(dbc.Button('Выбрать все',id='All plast',n_clicks=0,color="info",className='me-1'),align='center',style={'margin-bottom':'15px'}), #кнопка plast,style={'margin-bottom':'5px'}
        dbc.Col([
            html.H6('Фильтр пластов для ИИ:'),
            dcc.Loading(type="default",children=[html.Div(plast_selector_ai, style={'width':'400px','margin-bottom':'20px'})])],align='center'),
        html.Hr()
    ]),
    dbc.Row([
        html.Div([
            dbc.Button(html.Div(['Показать фильтры по залежам и кустам']),id="collapse-button-zalej_kust",className="mb-3",n_clicks=0), 
            dbc.Collapse([
                html.H6('Фильтр залежей:'),
                dcc.Loading(type="default",children=[html.Div(dcc.Dropdown(id='zalej-selector',multi=True), style={'width':'400px','margin-bottom':'10px'})]),
                html.H6('Фильтр кустов:'), 
                dcc.Loading(type="default",children=[html.Div(dcc.Dropdown(id='kust-selector',multi=True), style={'width':'400px','margin-bottom':'10px'})])
                ], id="collapse-zalej_kust",is_open=False)],style={'width':'600px','margin-bottom':'10px'}),
        html.Hr()   
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Button("Показать фильтры по ГФХ",id="collapse-button-gfh",className="mb-3",n_clicks=0),
            dbc.Collapse([
                html.H6('Выбор диапазона Kпр, мД:'),
                html.Div(dcc.Loading(type="default", children=[perm_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}), #слайдеры обернуты в загрузчики
                html.H6('Выбор диапазона Нэф, м:'),
                html.Div(dcc.Loading(type="default", children=[hef_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}),
                html.H6('Выбор диапазона ННТ, м:'),
                html.Div(dcc.Loading(type="default", children=[hoil_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}),
                html.H6('Выбор диапазона Soil, д.ед.:'),
                html.Div(dcc.Loading(type="default", children=[soil_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}),
                ], id="collapse-gfh",is_open=False),
                ]),
        dbc.Col([
            dbc.Button("Показать фильтры по PVT",id="collapse-button-pvt",className="mb-3",n_clicks=0),
            dbc.Collapse([
                html.H6('Выбор диапазона ГФ, м3/т:'),
                html.Div(dcc.Loading(type="default", children=[rs_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}), #слайдеры обернуты в загрузчики
                html.H6('Выбор диапазона Вязкости, мПас:'),
                html.Div(dcc.Loading(type="default", children=[mu_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}),
                ], id="collapse-pvt",is_open=False),
                ]),
        dbc.Col([
            dbc.Button("Показать фильтры по заканчиванию",id="collapse-button-well_filter",className="mb-3",n_clicks=0),
            dcc.Store(id='fact_data-slide-filtering'),
            dcc.Store(id='ai_data-slide-filtering'),
            dbc.Collapse([
                html.H6('Выбор диапазона длин Lгс:'),
                html.Div(dcc.Loading(type="default", children=[lgs_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}), #слайдеры обернуты в загрузчики
                html.H6('Выбор диапазона числа стадий:'),
                html.Div(dcc.Loading(type="default", children=[nfrac_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}),
                html.H6('Выбор диапазона тоннажа на стадию:'),
                html.Div(dcc.Loading(type="default", children=[mprop_slider]), style={'width':'350','margin-top':'8px','margin-bottom':'3px'}),
                ],id="collapse-well_filter",is_open=False),
                ]),
            ]),
    dbc.Row([
        html.Hr(),
        dbc.Col([
            html.H6('Выбор профиля:'),
            html.Div(profil_selector, style={'width':'400px','margin-bottom':'10px'}),
                ]),
        dbc.Col([
            html.H6('Выбор шага:'),
            html.Div(dcc.RadioItems([{'label': 'По годам', 'value': 'Годы'},
                                     {'label': 'По месяцам', 'value': 'Месяцы'}],'Годы',id='step-rb')), #выбор шага графиков (годы/месяцы)
                ]),        
        dbc.Col([
            html.H6('Выбор нормировочных множителей:'),
            dbc.Button('Проницаемость (ГИС)',id='udeln perm',n_clicks=0,className='mr-3', style={"margin-right": "10px",'margin-bottom':'0px'}),
            dbc.Button('ННТ',id='udeln hoil',n_clicks=0,className='mr-3',                 style={"margin-right": "10px",'margin-bottom':'0px'}),
            dbc.Button('Hэф',id='udeln heff',n_clicks=0,                                  style={"margin-right": "10px",'margin-bottom':'0px'}),
            dbc.Button('Число стадий',id='udeln nfrac',n_clicks=0,className='mr-3',       style={"margin-right": "10px",'margin-bottom':'0px'}),
            dbc.Button('Масса проппанта',id='udeln mprop',n_clicks=0,className='mr-3',    style={"margin-right": "10px",'margin-bottom':'0px'}),
            dbc.Button('1/Вязкость',id='udeln 1/mu',n_clicks=0,className='mr-3',          style={"margin-right": "10px",'margin-bottom':'10px'}),
                ],width=7),
        html.Hr()                    
    ]),
    dbc.Tabs([
        dbc.Tab(tab1_content,label='Верификация профилей',tab_id="tab-1"),
        dbc.Tab(tab2_content,label='Аналитика факта',tab_id="tab-2"),
        dbc.Tab(tab3_content,label='Аналитика МВР',tab_id="tab-3"),
    ],id='tabs', active_tab="tab-1")   # 
    ],
    style={'margin-left':'60px',
           'margin-right':'30px'})

#----------------------------калбэки для изменения в фильтрах пласта/мр, при выборе мр/кластера----------------------------------------
# Обновление второго выпадающего списка в зависимости от кластера
@app.callback(
     Output('field-selector', 'options'),
    [State('upload fact data', 'filename')],
    [Input('cluster-selector', 'value')])
def update_field_selector(file_name,cluster):
    if file_name is not None:
        fact_data = read_file(file_name,'lite') 
        values=list(fact_data['Месторождение'].loc[fact_data['Кластер'].isin(cluster)].unique()) # список месторождений из Df
        return [{'label': i, 'value': i} for i in values]
    else:
        return {}

# Обновление третьего выпадающего списка в завис имости от месторождения===============================================================
@app.callback(
     Output('plast-selector', 'options'),
    [State('upload fact data', 'filename')],
    [Input('field-selector', 'value')])
def update_horizon_selector(file_name,field):
    if file_name is not None:
        fact_data = read_file(file_name,'lite') 
        values=list(fact_data['Пласт'].loc[fact_data['Месторождение'].isin(field)].unique()) # список пластов из Df
        return [{'label': i, 'value': i} for i in values]
    else:
        return {} 
#----------------------------------------------------------------------------------ДЛЯ ИИ----------------------------------------------------------------------------------
# Обновление второго выпадающего списка в зависимости от кластера                       
@app.callback(
     Output('field-selector-ai', 'options'),
    [State('upload ai data', 'filename')],
    [Input('cluster-selector-ai', 'value')]) #можно сделать зависимым от фильтра по кластерам факта
def update_field_selector_ai(file_name,cluster):
    if file_name is not None:
        ai_forecast = read_file(file_name,'lite')[['Месторождение','Кластер']]
        values=list(ai_forecast['Месторождение'].loc[ai_forecast['Кластер'].isin(cluster)].unique()) # список месторождений из Df
        return [{'label': i, 'value': i} for i in values]
    else:
        return {}

# Обновление третьего выпадающего списка в зависимости от месторождения 
@app.callback(
     Output('plast-selector-ai', 'options'),
    [State('upload ai data', 'filename')],
    [Input('field-selector-ai', 'value')])
def update_horizon_selector_ai(file_name,field):
    if file_name is not None:
        ai_forecast = read_file(file_name,'lite')[['Месторождение','Пласт']]
        values=list(ai_forecast['Пласт'].loc[ai_forecast['Месторождение'].isin(field)].unique()) # список пластов из Df
        return [{'label': i, 'value': i} for i in values]
    else:
        return {}
    
#==========================================================================================СЛАЙДЕРЫ======================================================================================
#обновление range slider в зависимости от загружаемого df
@app.callback(
    [#Заканчивание
     Output('lgs-slider', 'value'),   Output('lgs-slider', 'min'), Output('lgs-slider', 'max'),
     Output('nfrac-slider', 'value'), Output('nfrac-slider', 'min'), Output('nfrac-slider', 'max'),
     Output('mprop-slider', 'value'), Output('mprop-slider', 'min'),Output('mprop-slider', 'max'),
     #ГФХ
     Output('perm-slider', 'value'), Output('perm-slider', 'min'),Output('perm-slider', 'max'),
     Output('hef-slider', 'value'), Output('hef-slider', 'min'),Output('hef-slider', 'max'),
     Output('hoil-slider', 'value'), Output('hoil-slider', 'min'),Output('hoil-slider', 'max'),
     Output('soil-slider', 'value'), Output('soil-slider', 'min'),Output('soil-slider', 'max'),
     # PVT
     Output('rs-slider', 'value'), Output('rs-slider', 'min'),Output('rs-slider', 'max'),
     Output('mu-slider', 'value'), Output('mu-slider', 'min'),Output('mu-slider', 'max')],

    [State('upload fact data', 'filename')],
    [Input('field-selector', 'value'),
     Input('plast-selector', 'value')])

def update_slider(fact_filename,field,horizon):
    if (fact_filename is not None) and (len(horizon)!=0):
        fact_data = read_file(fact_filename,'full') 
        chart_df=fact_data[(fact_data['Месторождение'].isin(field)) & (fact_data['Пласт'].isin(horizon))]

    # Устанавливаем новое мин и макс значение 
        return ([chart_df['Длина горизонтального ствола'].min(),chart_df['Длина горизонтального ствола'].max()],
                 chart_df['Длина горизонтального ствола'].min(),chart_df['Длина горизонтального ствола'].max(),
                [chart_df['Число стадий'].min(),chart_df['Число стадий'].max()],
                 chart_df['Число стадий'].min(),chart_df['Число стадий'].max(),
                [chart_df['Масса проппанта на стадию'].min(),chart_df['Масса проппанта на стадию'].max()],
                 chart_df['Масса проппанта на стадию'].min(),chart_df['Масса проппанта на стадию'].max(),

                [chart_df['Средняя проницаемость (ГИС)'].min(),chart_df['Средняя проницаемость (ГИС)'].max()],
                 chart_df['Средняя проницаемость (ГИС)'].min(),chart_df['Средняя проницаемость (ГИС)'].max(),
                [chart_df['Средняя эффективная мощность коллектора (ГИС)'].min(),chart_df['Средняя эффективная мощность коллектора (ГИС)'].max()],
                 chart_df['Средняя эффективная мощность коллектора (ГИС)'].min(),chart_df['Средняя эффективная мощность коллектора (ГИС)'].max(),
                [chart_df['Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)'].min(),chart_df['Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)'].max()],
                 chart_df['Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)'].min(),chart_df['Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)'].max(),
                [chart_df['Средний коэффициент нефтенасыщенности (Кн)'].min(),chart_df['Средний коэффициент нефтенасыщенности (Кн)'].max()],
                 chart_df['Средний коэффициент нефтенасыщенности (Кн)'].min(),chart_df['Средний коэффициент нефтенасыщенности (Кн)'].max(),
                 
                [chart_df['Газовый фактор'].min(),chart_df['Газовый фактор'].max()],
                 chart_df['Газовый фактор'].min(),chart_df['Газовый фактор'].max(),
                [chart_df['Средняя вязкость флюида в пластовых условиях'].min(),chart_df['Средняя вязкость флюида в пластовых условиях'].max()],
                 chart_df['Средняя вязкость флюида в пластовых условиях'].min(),chart_df['Средняя вязкость флюида в пластовых условиях'].max())
    else:
        return [-100,0],-100,0,[-1,0],-1,0,[-10,0],-10,0,[-10,0],-10,0,[-10,0],-10,0,[-10,0],-10,0,[-10,0],-10,0,[-10,0],-10,0,[-10,0],-10,0

#кэширование 
@app.callback(
   [Output('fact_data-slide-filtering','data'), #Сохранение словаря фильтров
    Output('ai_data-slide-filtering','data')],
   [State('upload fact data', 'filename')],
   #объект разработки
   [Input('field-selector', 'value'),
    Input('plast-selector', 'value'),
    Input('field-selector-ai', 'value'),
    Input('plast-selector-ai', 'value'),
    #заканчивание
    Input('lgs-slider','value'),
    Input('nfrac-slider','value'),
    Input('mprop-slider','value'),
    #гфх
    Input('perm-slider','value'),
    Input('hef-slider','value'),
    Input('hoil-slider','value'),
    Input('soil-slider','value'),
    #pvt
    Input('rs-slider','value'),
    Input('mu-slider','value')])    

def dict_columns_viborka(fact_filename,field,horizon,field_ai,horizon_ai,lgs,nfrac,mprop,perm,hef,hoil,soil,rs,mu):
    if (fact_filename is not None) and (horizon is not None):
        columns_viborka_fact = {'Месторождение':field,
                                'Пласт':horizon,
                                #'Годы':[1,2,3,4,5,6,7,8,9,10],
                                'Длина горизонтального ствола':lgs,
                                'Число стадий':nfrac,
                                'Масса проппанта на стадию':mprop,
                                'Средняя проницаемость (ГИС)':perm,
                                'Средняя эффективная мощность коллектора (ГИС)':hef,
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)':hoil,
                                'Средний коэффициент нефтенасыщенности (Кн)':soil,
                                'Газовый фактор':rs,
                                'Средняя вязкость флюида в пластовых условиях':mu}
        columns_viborka_ai=columns_viborka_fact.copy()
        columns_viborka_ai['Месторождение']=field_ai
        columns_viborka_ai['Пласт']=horizon_ai
        #if 'ПНГ, млн м3' in chart_df.columns: #проверка на ии или факт/гдм данные
        #    columns_exp_gas=columns_exp+['ГФ, м3/т','Накопленный ПНГ, млн м3']
        #    chart_df[[*columns_exp_gas]].to_pickle(os.path.join(UPLOAD_DIRECTORY, fact_filename.split('.')[0]+'_lite-filter.pickle'))
        #else:
        #    chart_df[[*columns_exp]].to_pickle(os.path.join(UPLOAD_DIRECTORY, fact_filename.split('.')[0]+'_lite-filter.pickle'))

        #return fact_filename.split('.')[0]+'_lite-filter.pickle'
        return json.dumps(columns_viborka_fact),json.dumps(columns_viborka_ai)
    else:
        return {'py':'empty'},{'py':'empty'}

#param_col=['Месторождение','Пласт','Скважина', 
#           'Средняя проницаемость (ГИС)','Средний коэффициент нефтенасыщенности (Кн)','Средняя эффективная мощность коллектора (ГИС)',
#           'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)','Газовый фактор','Начальное пластовое давление','Средняя вязкость флюида в пластовых условиях',
#           'Градиент начального давления закрытия, атм/м','Градиент горизонтального напряжения, атм/м',
#           'Средний динамический модуль Юнга для песчаника','Средний динамический коэффициент Пуассона для алевролита/аргиллита',
#           'Средний динамический модуль Юнга для алевролита/аргиллита','Средний динамический коэффициент Пуассона для песчаника',
#           'Расстояние между рядами скважин','Тип ГРП','Длина горизонтального ствола','Масса проппанта на стадию','Число стадий','Число стадий NGT']

def make_viborka_df(chart_df,dict_viborka,step):
    field,horizon,lgs,nfrac,mprop,perm,hef,hoil,soil,rs,mu=dict_viborka.values()
    df_viborka = chart_df[(chart_df['Месторождение'].isin(field)) &
                          (chart_df['Пласт'].isin(horizon)) &
                          #(chart_df['Годы'].isin(range(1, 11))) &
                          #заканчивание
                          (chart_df['Длина горизонтального ствола'].between(lgs[0], lgs[1])) &
                          (chart_df['Число стадий'].between(nfrac[0], nfrac[1])) &
                          (chart_df['Масса проппанта на стадию'].between(mprop[0], mprop[1])) &
                          #ГФХ
                          (chart_df['Средняя проницаемость (ГИС)'].between(perm[0], perm[1])) &
                          (chart_df['Средняя эффективная мощность коллектора (ГИС)'].between(hef[0], hef[1])) &
                          (chart_df['Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)'].between(hoil[0], hoil[1])) &
                          (chart_df['Средний коэффициент нефтенасыщенности (Кн)'].between(soil[0], soil[1])) &
                          #PVT
                          (chart_df['Газовый фактор'].between(rs[0], rs[1])) &
                          (chart_df['Средняя вязкость флюида в пластовых условиях'].between(mu[0], mu[1]))]
    #выбор шага=Год
    if (step=='Годы') and ('Годы' not in df_viborka.columns):
        df_viborka['Годы']=(df_viborka['Месяцы'] - 1) // 12 + 1 #считаем года
        #print('1',df_viborka[df_viborka['Скважина']=='22105'][['Скважина','Месяцы','Годы','Нефть, тыс т']]) #test
        well_param = df_viborka.drop_duplicates(['Месторождение', 'Пласт', 'Скважина']) #[param_col]
        df_viborka = (df_viborka.groupby(['Кластер', 'Месторождение', 'Пласт', 'Скважина', 'Годы'],as_index=False)
                                .agg({'Нефть, тыс т': 'sum', 
                                      'Жидкость, тыс т': 'sum', 
                                      'Жидкость, тыс м3': 'sum',
                                      'ПНГ, млн м3': 'sum', 
                                      'Время работы': 'sum', 
                                      'Месяцы': 'count'}).merge(well_param, on=['Месторождение', 'Пласт', 'Скважина'], suffixes=('', '_right'))) #добавляем правым столбцам  '_right'
        #print('2',df_viborka[df_viborka['Скважина']=='22105'][['Скважина','Месяцы','Годы','Нефть, тыс т']]) #test
        #расчитываем оставшиеся показатели разработки
        df_viborka['Qн, т/сут (МЭР)']=df_viborka['Нефть, тыс т']/df_viborka['Время работы']*1000*24
        df_viborka['Qж, м3/сут (МЭР)']=df_viborka['Жидкость, тыс м3']/df_viborka['Время работы']*1000*24
        df_viborka['Qж, т/сут (МЭР)']=df_viborka['Жидкость, тыс т']/df_viborka['Время работы']*1000*24
        #приравнял для простоты
        df_viborka['Qн, т/сут (МЭР)']=df_viborka['Qн, т/сут (ТР)']
        df_viborka['Qж, м3/сут (МЭР)']= df_viborka['Qж, м3/сут (ТР)']
        df_viborka['Qж, т/сут (МЭР)']=df_viborka['Qж, т/сут (ТР)']

        df_viborka = df_viborka.drop(columns=[col for col in df_viborka.columns if col.endswith('_right')]) # Удаление столбцов с суффиксами '_right'
        df_viborka= df_viborka[(df_viborka['Месяцы'] % 12 == 0) & # те месяц 12,24,36..
                               (df_viborka['Годы'].isin(range(1, 30)))].reset_index(drop=True) #берем только за целые года.
        df_viborka[['Темп падения Qн','Темп падения Qж']]=df_viborka[['Qн, т/сут (МЭР)','Qж, м3/сут (МЭР)']] / df_viborka.loc[df_viborka['Годы']==1,
                                                                        ['Qн, т/сут (МЭР)','Qж, м3/сут (МЭР)']].reindex(pd.RangeIndex(start=0, stop=len(df_viborka))).fillna(method='ffill')

    elif step=='Месяцы':
        df_viborka[['Темп падения Qн','Темп падения Qж']]=df_viborka[['Qн, т/сут (МЭР)','Qж, м3/сут (МЭР)']] / df_viborka.loc[df_viborka['Месяцы']==1,
                                                                        ['Qн, т/сут (МЭР)','Qж, м3/сут (МЭР)']].reindex(pd.RangeIndex(start=0, stop=len(df_viborka))).fillna(method='ffill')
    return df_viborka


#калбэк для экспорта таблицы по средним профилям
@app.callback(
    Output('profil-table-download','data'),
    [State('upload fact data', 'filename')],
    [Input('profil-export-button', 'n_clicks'),
     Input('field-selector', 'value'),
     Input('plast-selector', 'value'),
     Input('lgs-slider','value'),
     Input('nfrac-slider','value'),
     Input('mprop-slider','value'),
     Input('profil-selector', 'value'),

     Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac', 'n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff', 'n_clicks'),
     Input('udeln mprop', 'n_clicks'),
     Input('udeln 1/mu', 'n_clicks')])

def export_profils_to_excel(fact_filename,n_click,field,horizon,lgs,nfrac,mprop,profil,click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu):
    if n_click > 0 and fact_filename is not None:
        chart_df=read_file(fact_filename,'lite')
        chart_df = chart_df[(chart_df['Месторождение'].isin(field)) &
                            (chart_df['Пласт'].isin(horizon)) &
                            (chart_df['Годы'].isin(range(1, 11))) &
                            (chart_df['Длина горизонтального ствола'].between(lgs[0], lgs[1])) &
                            (chart_df['Число стадий'].between(nfrac[0], nfrac[1])) &
                            (chart_df['Масса проппанта на стадию'].between(mprop[0], mprop[1]))]
        #добавление удельных================
        ctx = callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        if trigger_id:
            button_states = [click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu]
            selected_buttons = [i for i, state in enumerate(button_states, start=1) if state % 2 != 0]
            if selected_buttons:
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                'Средняя эффективная мощность коллектора (ГИС)','Масса проппанта на стадию','1/Вязкость'] 
                divisor = chart_df[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                chart_df[profil]=chart_df[profil] / divisor
        #расчет табличек=================================

        chart_obj_cl = chart_df.pivot_table(index='Годы', columns=['Кластер'], values=profil, aggfunc='mean') #mean for cluster
        chart_obj_cl_well = chart_df.pivot_table(index='Годы', columns=['Кластер'], values='Скважина', aggfunc='count') #num well for clustr

        chart_obj_field = chart_df.pivot_table(index='Годы', columns=['Кластер','Месторождение'], values=profil, aggfunc='mean') #mean for field
        chart_obj_field_well = chart_df.pivot_table(index='Годы', columns=['Кластер','Месторождение'], values='Скважина', aggfunc='count') #num well for field

        chart_obj_horizon = chart_df.pivot_table(index='Годы', columns=['Месторождение','Пласт'], values=profil, aggfunc='mean') #mean for horiz
        chart_obj_horizon_well = chart_df.pivot_table(index='Годы', columns=['Месторождение','Пласт'], values='Скважина', aggfunc='count') #num well for horiz
        #запаковка табличек в один словарь================
        dataframes = {
                    'Профиля по кластерам': chart_obj_cl,
                    'Кол-во скважин по кластерам': chart_obj_cl_well,
                    'Профиля по месторождениям': chart_obj_field,
                    'Кол-во скважин по месторождениям': chart_obj_field_well,
                    'Профиля по пластам': chart_obj_horizon,
                    'Кол-во скважин по пластам': chart_obj_horizon_well}
        
        #открытие файла и запись==========================
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, df in dataframes.items():
                df.to_excel(writer, sheet_name=sheet_name, index=True)
        output.seek(0)

        return dcc.send_bytes(output.read(), 'Профиля отчет.xlsx')
    else:
        return None

#-------------------------------------------калбэк для кнопок--------------------------------------------------------------------------
# Обработка нажатия кнопки "Выбрать все значения" Кластеры
@app.callback(
    Output('cluster-selector', 'value'),
    [Input('All cluster', 'n_clicks')],
    [State('cluster-selector', 'options')]
)
def select_all_fields(n_clicks, options):
    if n_clicks > 0:
        return [option['value'] for option in options]
    else:
        return []

# Обработка нажатия кнопки "Выбрать все значения" Месторождения
@app.callback(
    Output('field-selector', 'value'),
    [Input('All field', 'n_clicks')],
    [State('field-selector', 'options')]
)
def select_all_fields(n_clicks, options):
    if n_clicks > 0:
        return [option['value'] for option in options]
    else:
        return []
    
# Обработка нажатия кнопки "Выбрать все значения" пласты
@app.callback(
    Output('plast-selector', 'value'),
    [Input('All plast', 'n_clicks')],
    [State('plast-selector', 'options')]
)
def select_all_plasts(n_clicks, options):
    if n_clicks > 0:
        return [option['value'] for option in options]
    else:
        return []


#Покраска кнопок для удельных профилей
@app.callback(
    [Output('udeln perm', 'style'),
     Output('udeln nfrac', 'style'),
     Output('udeln hoil', 'style'),
     Output('udeln heff', 'style'),
     Output('udeln mprop', 'style'),
     Output('udeln 1/mu', 'style'),],
    [Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac', 'n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff','n_clicks'),
     Input('udeln mprop','n_clicks'),
     Input('udeln 1/mu', 'n_clicks'),

     Input('profil-selector','value')]
)
def update_button_styles(click1, click2, click3, click4, click5,click6,profil):
    if profil not in ['ГФ, м3/т','Обв, %']:
        button_styles = [{'background-color': 'blue' if click1 % 2 != 0 else 'grey','margin-right':'10px'},
                         {'background-color': 'blue' if click2 % 2 != 0 else 'grey','margin-right':'10px'},
                         {'background-color': 'blue' if click3 % 2 != 0 else 'grey','margin-right':'10px'},
                         {'background-color': 'blue' if click4 % 2 != 0 else 'grey','margin-right':'10px'},
                         {'background-color': 'blue' if click5 % 2 != 0 else 'grey','margin-right':'10px'},
                         {'background-color': 'blue' if click6 % 2 != 0 else 'grey','margin-right':'10px'}]
    else:
        button_styles = [{'background-color': 'grey','margin-right':'10px'},
                         {'background-color': 'grey','margin-right':'10px'},
                         {'background-color': 'grey','margin-right':'10px'},
                         {'background-color': 'grey','margin-right':'10px'},
                         {'background-color': 'grey','margin-right':'10px'},
                         {'background-color': 'grey','margin-right':'10px'}]
    return button_styles

norm_mult={1:'/Кпр',2:'/Число стадий',3:'/ННТ',4:'/Нэф',5:'/Масса проппанта',6:'*Вязкость'} #не менять местами

# Калбэк очистки директории кэша
@app.callback(
         Output('cash button', 'outline'),
        [Input('cash button', 'n_clicks'),
         Input('upload fact data','filename'),
         Input('upload ai data','filename')])

def clear_directory(n_clicks,fact,ai):
    if n_clicks is not None and n_clicks > 0 and len(os.listdir(UPLOAD_DIRECTORY))==0:
        # проверяем, пустая ли директория UPLOAD_DIRECTORY
        if len(os.listdir(UPLOAD_DIRECTORY))!=0:
            # если директория пустая, меняем свойство outline кнопки на False
            return False
        else:
            # удаляем все файлы и поддиректории из директории UPLOAD_DIRECTORY
            for filename in os.listdir(UPLOAD_DIRECTORY):
                file_path = os.path.join(UPLOAD_DIRECTORY, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print('Failed to delete %s. Reason: %s' % (file_path, e))

            # если директория не пустая, меняем свойство outline кнопки на True
            return True

    # если кнопка не была нажата, возвращаем текущее значение свойства outline
    return True
#======================================================================#функции помощник препроцеса======================================================================#
 
# функция для удобного получения перцентилей/любой функции на вход:дф, профиль, функциия
def get_percentile(chart_df,profil,func,step):
    return chart_df.groupby(step,as_index=True,observed=True)[[profil]].agg(func).to_numpy().ravel()

#======================================================================Калбэк для загрузки ФАКТА, прогноза ИИ и МВР#======================================================================
@app.callback(                      
     Output('upload fact data', 'children'),    #fact сохраняется в кэш   
    [Input('upload fact data', 'contents')],
    [State('upload fact data', 'filename')])
def upload_fact_data(contents, filename):
    if contents is not None:
        save_file(filename, contents)
        return html.Div([html.H6(filename),html.H6('Файл загружен успешно ✅')])
    return html.Div(['Добавить файл с', html.B(' фактом/ГДМ')])

@app.callback(
     Output('upload ai data','children'),       #ai сохраняется в кэш
    [Input('upload ai data', 'contents')],
    [State('upload ai data', 'filename')])
def upload_ai_forecast(contents, filename):
    if contents is not None:
        save_file(filename, contents)
        return  html.Div([html.H6(filename),html.H6('Файл загружен успешно ✅')])
    return  html.Div(['Добавить файл с', html.B(' прогнозом ИИ')])

@app.callback(
     Output('upload mvr data','children'), #mvr сохраняется в кэш (пока предполагаем, что данные приходят в виде файла)
     Output('mvr-table', 'columnDefs'),
     Output('mvr-table', 'rowData'),       
    [Input('upload mvr data', 'contents')],
    [State('upload mvr data', 'filename')])
def upload_mvr_forecast(contents, filename):
    if contents is not None:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        if 'xlsx' in filename:
            mvr_data = pd.read_excel(io.BytesIO(decoded),skiprows=2) #используем skiprows
        elif 'csv' in filename:
            mvr_data = pd.read_csv(io.StringIO(decoded.decode('cp1251')), sep=";",skiprows=2) #используем skiprows
        elif 'pickle' in filename or 'pkl' in filename:
            mvr_data = pd.read_pickle(io.BytesIO(decoded),skiprows=2) #используем skiprows
        else:
            return 'Ошибка: неизвестный формат'
        
        params0=['Номер расчёта',
                 'Длина горизонтального ствола 1 в метрах','Тип ГРП Ствол 1','Расход ГРП 1','Количество стадий 1','Масса пропанта на стадию Ствол 1',
                 'НДН за 1 год, тыс.т',
                 'НДН за 10 лет, тыс.т',
                 'Qн 1 мес, т/сут',
                 'Qн 13 мес, т/сут',
                 #'Добыча нефти, тыс.т.',                             #доб 1 мес
                 #'Добыча нефти, тыс.т..12',                           #доб за 1 год
                 #'Добыча нефти, тыс.т..13',                          #доб 13 мес
                 #*[f'Добыча нефти, тыс.т..{25+i}' for i in range(9)] #доб 2-10 годы
        ]
        mvr_data['Номер расчёта']=np.arange(1,len(mvr_data)+1)
        mvr_data['НДН за 10 лет, тыс.т']=mvr_data[['Добыча нефти, тыс.т..12',*[f'Добыча нефти, тыс.т..{25+i}' for i in range(9)]]].sum(axis=1).round(2)
        mvr_data['НДН за 1 год, тыс.т']=mvr_data['Добыча нефти, тыс.т..12']/10*10
        mvr_data['Qн 1 мес, т/сут']=(mvr_data['Добыча нефти, тыс.т.']/30*1000).round(2)
        mvr_data['Qн 13 мес, т/сут']=(mvr_data['Добыча нефти, тыс.т..13']/30*1000).round(2)
        # Проверка наличия столбца "концентрация"
        if 'Концентрация' not in mvr_data.columns:
            # Добавление столбца "концентрация" со значениями "Ст"
            params0.append('Концентрация')
            mvr_data['Концентрация'] = 'Ст'
        mvr_data=mvr_data[params0]
        mvr_data=mvr_data.rename(columns={'Длина горизонтального ствола 1 в метрах':'Длина горизонтального ствола',
                                          'Тип ГРП Ствол 1':'Тип ГРП',
                                          'Расход ГРП 1':'Расход ГРП',
                                          'Количество стадий 1':'Количество стадий',
                                          'Масса пропанта на стадию Ствол 1':'Масса пропанта на стадию'})
                                          
        #данные остаются в горизонтальном виде (как у achwell)
        mvr_data.to_pickle(os.path.join(UPLOAD_DIRECTORY, filename.split('.')[0]+'_mvr.pickle'))

            # Вывод типов данных выбранных столбцов
        print("Типы данных выбранных столбцов:")
        for col in mvr_data.columns:
            print(f"{col}: {mvr_data[col].dtype}")

        # Преобразование данных для AG Grid
        column_defs = [{"headerName": col, "field": col} for col in mvr_data.columns]
        #column_defs = [{"headerName": col.replace(' ', '<br>'), "field": col} for col in obj_params.columns]
        #print(mvr_data.to_dict('records'))
        row_data = mvr_data.to_dict('records')

        return  html.Div([html.H6(filename),html.H6('Файл загружен успешно ✅')]), column_defs, row_data
    return  html.Div(['Добавить файл с', html.B(' расчётами МВР')]) , [] , []

#-------------------------------------------калбэк для графиков ТАБ1------------------------------------------------------------------------
#------------------------------------------ГИСТОГРАММА СТАРТОВЫХ ДЕБИТОВ (1ЫЙ ГОД)----------------------------------------------------------
data_columns=['Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)',
              'Средний коэффициент нефтенасыщенности (Кн)',
              'Средняя эффективная мощность коллектора (ГИС)',
              'Средняя проницаемость (ГИС)']  

#выбор колонок для расчета с отклонением (deviant)
data_columns=['Средняя проницаемость (ГИС)',
              'Средний коэффициент нефтенасыщенности (Кн)',
              'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)',
              'Средняя вязкость флюида в пластовых условиях',
              'Расстояние между рядами скважин',
              'Число стадий']
#@app.callback(
#    [Output('qstart histogram', 'figure'),
#     Output('deviat-sample-output','children')], #Данный callback возвращает количество отфильтр расчетов (в остальных такого нет)
#    [State('upload fact data', 'filename'),                 #подгрузка данных из кэша
#     State('upload ai data', 'filename')],
#
#    [Input('field-selector', 'value'),
#     Input('plast-selector', 'value'),
#
#     Input('lgs-slider','value'),
#     Input('nfrac-slider','value'),
#     Input('mprop-slider','value'),
#     Input('profil-selector', 'value'),
#     Input('year-slider', 'value'),
#     Input('field-selector-ai', 'value'),
#     Input('plast-selector-ai', 'value'),
#     Input('deviat-check','value'),
#     Input('deviat-slider','value')])

@app.callback(
    [Output('qstart histogram', 'figure'),
     Output('deviat-sample-output','children')], #Данный callback возвращает количество отфильтр расчетов (в остальных такого нет)
    [State('upload fact data', 'filename'),                 #подгрузка данных из кэша
     State('upload ai data', 'filename')],

    [Input('fact_data-slide-filtering','data'), #Подгрузка набора фильтров для факт выборки-тригер
     Input('ai_data-slide-filtering','data'),   #Подгрузка набора фильтров для прогн выборки-тригер

     Input('plast-selector', 'value'), #для тригера
     Input('plast-selector-ai', 'value'), #для тригера
     Input('profil-selector', 'value'),
     Input('step-rb', 'value'),
     Input('step-slider', 'value'),
     Input('deviat-check','value'),
     Input('deviat-slider','value')])

def qstart_histogram(fact_filename,ai_filename,fact_viborka,ai_viborka,horizon,horizon_ai,profil,step,step_slider,deviat_chek,percent):
    if (fact_filename is None) or (horizon is None):
        return go.Figure(), html.Div(html.H6('Данные не были загружены'))
    #сверху проерка на отсутствие данных, далее все как и раньше
    data=json.loads(fact_viborka)
    chart_df=make_viborka_df(read_file(fact_filename,'lite'),data,step)

    chart_df=chart_df[chart_df[step]==step_slider] #выобр за n=step_slider год или месяц
    #
    len1=len(chart_df['Скважина'].unique()) #изначально кол-во скважин те расчтов гдм
    
    if deviat_chek:
        mean_values = chart_df[data_columns].mean() # Вычислить среднее значение для каждого столбца
        lower_bound = mean_values * (1-percent/100)
        upper_bound = mean_values * (1+percent/100)
        chart_df = chart_df[chart_df[data_columns].apply(lambda x: x.between(lower_bound[x.name], upper_bound[x.name])).all(axis=1)] #Отфильтровать DF методом .between

    len2=len(chart_df['Скважина'].unique()) #конечное кол-во скважин/расчтов гдм
    bins=np.linspace(0,chart_df[profil].max()+1,50)
    fig = px.histogram(chart_df,x=profil,color='Пласт',opacity=0.6, nbins=50) #50

    if (len(horizon)!=0) & (len(chart_df)!=0):
        fig.add_trace(go.Scatter(x=[np.percentile(chart_df[profil], 90)], y=[0],
                            name='Факт P10',mode='markers',marker=dict(size=15,color='red',symbol='0'),
                            hovertemplate=f"Факт Р10, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f} "+f"{label_dict[profil][1]}<extra></extra>"))

        fig.add_trace(go.Scatter(x=[np.percentile(chart_df[profil], 50)], y=[0],
                            name='Факт P50',mode='markers',marker=dict(size=15,color='yellow',symbol='0'),
                            hovertemplate=f"Факт Р50, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f} "+f"{label_dict[profil][1]}<extra></extra>"))
                
        fig.add_trace(go.Scatter(x=[np.percentile(chart_df[profil], 10)], y=[0],
                            name='Факт P90',mode='markers',marker=dict(size=15,color='mediumseagreen',symbol='0'),
                            hovertemplate=f"Факт Р90, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f} "+f"{label_dict[profil][1]}<extra></extra>"))    
    #----------------------Использование даннных прогноза ИИ--------------------------------
    if (ai_filename is not None) and (horizon_ai is not None):
        data=json.loads(ai_viborka)
        ai_forecast=make_viborka_df(read_file(ai_filename,'lite'),data,step)
        ai_forecast=ai_forecast.loc[ai_forecast[step]==step_slider] #выобр за n=step_slider год или месяца
        
        ai_forecast_bins=pd.cut(ai_forecast[profil],
                                bins=bins, #от 0 до 499 тыс.т step=1
                                labels=bins[:-1]).value_counts().sort_index() #.replace(0,np.nan).dropna()
        
        fig.add_trace(go.Scatter(x=np.array(ai_forecast_bins.index),y=ai_forecast_bins,
                                 name="Прогноз ИИ",mode='markers+lines',marker=dict(size=3,color='black',symbol='0'),
                                 hovertemplate=f"Прогноз ИИ, {step_slider} год:<br>"+"%{x:.2f} "+f"{label_dict[profil][1]}<br>"+"count=%{y:.0f}"+"<extra></extra>"))

        ''
        #fig.add_trace(go.Scatter(x=x,y=np.zeros_like(x),
        #                         name="Прогноз ИИ",mode='markers',marker=dict(size=7,color='black',symbol='0'),
        #                         hovertemplate=f"Прогноз ИИ, {step_slider} год:<br>"+"%{x:.2f} "+f"{label_dict[profil][1]}<br>"+"<extra></extra>"))
        ''
        fig.add_trace(go.Scatter(x=[np.percentile(ai_forecast[profil], 50)],y=[0],
                                 name="Прогноз ИИ P50",mode='markers',marker=dict(size=15,color='black',symbol='x'),
                                 hovertemplate=f"Прогноз ИИ P50, {step_slider}"+ f"{'год'}[step]:<br>"+"%{x:.2f} "+f"{label_dict[profil][1]}<br>"+"<extra></extra>"))
        #"Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"
    #-------------------------------------------------------------------------------------------------------------------------------------------    
    fig.update_layout(
        xaxis1=dict(title=f"{label_dict[profil][0]} в {step_slider}-й "+ {'Годы':'год','Месяцы':'месяц'}[step]+f", {label_dict[profil][1]}"),
        yaxis1=dict(title=f'Кол-во'),height=550)
        #title=dict(text=f'Стартовая добыча 1-ый год')
    return fig, html.Div(html.H6(f'Выбраны {len2} из {len1} расчета'))
#------------------------------------------ГИСТОГРАММА УДЕЛЬНЫХ СТАРТОВЫХ ДЕБИТОВ (1ЫЙ ГОД)-----------------------------------------------------
@app.callback(
     Output('udeln qstart histogram','figure'),
    [State('upload fact data', 'filename'),                 #подгрузка данных из кэша
     State('upload ai data', 'filename')],

    [Input('fact_data-slide-filtering','data'), #Подгрузка набора фильтров для факт выборки-тригер
     Input('ai_data-slide-filtering','data'),   #Подгрузка набора фильтров для прогн выборки-тригер

     Input('plast-selector', 'value'), #для тригера
     Input('plast-selector-ai', 'value'), #для тригера
     Input('profil-selector', 'value'),
     Input('step-rb', 'value'),
     Input('step-slider', 'value'),

     Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac', 'n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff', 'n_clicks'),
     Input('udeln mprop', 'n_clicks'),
     Input('udeln 1/mu', 'n_clicks'),
     Input('deviat-check','value'),
     Input('deviat-slider','value')])

def udeln_qstart_histogram(fact_filename,ai_filename,fact_viborka,ai_viborka,horizon,horizon_ai,profil,step,step_slider,
                           click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu,deviat_check,percent):
    if (fact_filename is None) or (horizon is None):
        return go.Figure()
    #сверху проерка на отсутствие данных, далее все как и раньше 
    data=json.loads(fact_viborka)
    chart_df=make_viborka_df(read_file(fact_filename,'lite'),data,step)

    chart_df=chart_df[chart_df[step]==step_slider] #выобр за n=step_slider год или месяц
    #

    if deviat_check:
        mean_values = chart_df[data_columns].mean()
        # Вычислить среднее значение для каждого столбца
        lower_bound = mean_values * (1-percent/100)
        upper_bound = mean_values * (1+percent/100)
        # Отфильтровать DataFrame с использованием метода .between
        chart_df = chart_df[chart_df[data_columns].apply(lambda x: x.between(lower_bound[x.name], upper_bound[x.name])).all(axis=1)]
    #
    if profil not in ['ГФ, м3/т','Обв, %']: #профиля в списке не нормируем 
    #_____________________________________________________
        ctx = callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        if trigger_id:
            button_states = [click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu]
            selected_buttons = [i for i, state in enumerate(button_states, start=1) if state % 2 != 0]
            if selected_buttons: #если не пустые
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                'Средняя эффективная мощность коллектора (ГИС)','Масса проппанта на стадию','1/Вязкость']
                divisor = chart_df[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                chart_df[profil]=chart_df[profil] / divisor
    #_____________________________________________________
        if (len(horizon)!=0) & (len(chart_df)!=0):
            fig =px.histogram(chart_df,x=profil,color='Пласт',opacity=0.6, nbins=50) # 

            fig.add_trace(go.Scatter(x=[np.percentile(chart_df[profil], 90)], y=[0],
                            name='Удельн. факт P10',mode='markers',marker=dict(size=15,color='red',symbol='0'),
                            hovertemplate=f"Удельн. факт Р10, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f}<extra></extra>"))

            fig.add_trace(go.Scatter(x=[np.percentile(chart_df[profil], 50)], y=[0],
                            name='Удельн. факт P50',mode='markers',marker=dict(size=15,color='yellow',symbol='0'),
                            hovertemplate=f"Удельн. факт Р50, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f}<extra></extra>"))
           
            fig.add_trace(go.Scatter(x=[np.percentile(chart_df[profil], 10)], y=[0],
                            name='Удельн. факт P90',mode='markers',marker=dict(size=15,color='mediumseagreen',symbol='0'),
                            hovertemplate=f"Удельн. факт Р90, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f}<extra></extra>")) 

            #----------------------Использование даннных прогноза ИИ------------------------------
            if (ai_filename is not None) and (horizon_ai is not None):
                data=json.loads(ai_viborka)
                ai_forecast=make_viborka_df(read_file(ai_filename,'lite'),data,step)
                ai_forecast=ai_forecast.loc[ai_forecast[step]==step_slider] #выобр за n=step_slider год или месяца

                if selected_buttons: #если не пустые
                    divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                    'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                    'Средняя эффективная мощность коллектора (ГИС)','Масса проппанта на стадию','1/Вязкость'] 
                    divisor_ai = ai_forecast[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                    ai_forecast[profil]=ai_forecast[profil] / divisor_ai #делаем удельные 

                ai_forecast_bins=pd.cut(ai_forecast[profil],
                                    bins=np.linspace(0,ai_forecast[profil].max()+1,50), #от 0 до 499 тыс.т step=1
                                    labels=np.linspace(0.5,ai_forecast[profil].max()+1,49)).value_counts().sort_index() #.replace(0,np.nan).dropna()
                fig.add_trace(go.Scatter(x=np.array(ai_forecast_bins.index),y=ai_forecast_bins,
                                 name="Удельн. прогноз ИИ",mode='markers+lines',marker=dict(size=7,color='black',symbol='0'),
                                 hovertemplate=f"Удельн. прогноз ИИ, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f} "+f"{label_dict[profil][1]}<br>"+"<extra></extra>"))
                
                fig.add_trace(go.Scatter(x=[np.percentile(ai_forecast[profil], 50)],y=[0],
                                 name="Удельн. прогноз ИИ P50",mode='markers',marker=dict(size=15,color='black',symbol='x'),
                                 hovertemplate=f"Удельн. прогноз ИИ P50, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f} "+f"{label_dict[profil][1]}<br>"+"<extra></extra>"))
                #''
                #fig.add_trace(go.Scatter(x=ai_forecast[profil],y=np.zeros_like(ai_forecast[profil]),
                #                 name="Удельн. прогноз ИИ",mode='markers',marker=dict(size=7,color='black',symbol='0'),
                #                 hovertemplate=f"Удельн. прогноз ИИ, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f} "+f"{label_dict[profil][1]}<br>"+"<extra></extra>"))
                #
                #fig.add_trace(go.Scatter(x=[np.percentile(x, 50)],y=np.zeros_like(x),
                #                 name="Удельн. прогноз ИИ P50",mode='markers',marker=dict(size=15,color='black',symbol='x'),
                #                 hovertemplate=f"Удельн. прогноз ИИ P50, {step_slider} "+{'Годы':'год:','Месяцы':'месяц:'}[step]+"<br>%{x:.2f} "+f"{label_dict[profil][1]}<br>"+"<extra></extra>"))
            #---------------------------------------------------------------------------------------
            fig.update_layout(
                xaxis=dict(title=f'{label_dict[profil][0]} удельная в {step_slider}-й'+{'Годы':'год','Месяцы':'мес.'}[step]+f', {label_dict[profil][0]+"".join([norm_mult[i] for i in selected_buttons])}'),
                yaxis=dict(title=f'Кол-во'),height=550)
            return fig
        else:
            return go.Figure()
    else:
        return go.Figure()

#------------------------------------------ГРАФИК ПРОФИЛЕЙ------------------------------------------------------------------------
#@app.callback(
#    Output('profils', 'figure'),
#    #[State('data-slide-filtering','data'),
#     [State('upload fact data','filename'),
#     State('upload ai data', 'filename'),
#
#     #Input('field-selector', 'value'),
#     State('plast-selector', 'value')],
#     #Input('lgs-slider','value'),
#     #Input('nfrac-slider','value'),
#     #Input('mprop-slider','value'),
#
#     [Input('profil-selector', 'value'),
#     Input('profil-rb', 'value'),
#
#     Input('field-selector-ai', 'value'),
#     Input('plast-selector-ai', 'value')])
#
#     #Input('deviat-check','value'),
#     #Input('deviat-slider','value')])
@app.callback(
    Output('profils', 'figure'),
    [State('upload fact data', 'filename'),
     State('upload ai data', 'filename')],

    [Input('fact_data-slide-filtering','data'), #Подгрузка набора фильтров для факт выборки-тригер
     Input('ai_data-slide-filtering','data'),   #Подгрузка набора фильтров для прогн выборки-тригер

     Input('plast-selector', 'value'), #для тригера
     Input('plast-selector-ai', 'value'), #для тригера
     Input('profil-selector', 'value'),
     Input('step-rb', 'value'),
     Input('profil-rb', 'value')])

#def q_profils(df_name_slider_filter,fact_filename,ai_filename,field,horizon,lgs,nfrac,mprop,profil,graph,field_ai,horizon_ai,deviat_chek,percent):
def q_profils(fact_filename,ai_filename,fact_viborka,ai_viborka,horizon,horizon_ai,profil,step,graph):
    if (fact_filename is None) or (horizon is None):
        return go.Figure()
    
    data=json.loads(fact_viborka)
    chart_df=make_viborka_df(read_file(fact_filename,'lite'), data, step) #открываем файл из кэша и сразу применяем фильтры из словаря в функции make_viborka_df()
    if step=='Месяцы':
        chart_df=chart_df[chart_df['Месяцы'].isin(range(1,37))]
    #if deviat_chek:
    #    mean_values = chart_df[data_columns].mean()
    #    # Вычислить среднее значение для каждого столбца
    #    lower_bound = mean_values * (1-percent/100)
    #    upper_bound = mean_values * (1+percent/100)
    #    # Отфильтровать DataFrame с использованием метода .between
    #    chart_df = chart_df[chart_df[data_columns].apply(lambda x: x.between(lower_bound[x.name], upper_bound[x.name])).all(axis=1)]
    #
    colors = px.colors.qualitative.Plotly[:len(chart_df['Пласт'].unique())]
    color_map = dict(zip(chart_df['Пласт'].unique(), colors))
    chart_df['Цвет пласт'] = chart_df['Пласт'].map(color_map)

    if len(horizon)!=0 and len(chart_df)!=0:
        p10=get_percentile(chart_df,profil,[lambda x: np.percentile(x, 90)],step)
        p50=get_percentile(chart_df,profil,[lambda x: np.percentile(x, 50)],step)
        p90=get_percentile(chart_df,profil,[lambda x: np.percentile(x, 10)],step)
        p_max=get_percentile(chart_df,profil,'max',step)   
        p_min=get_percentile(chart_df,profil,'min',step)
    else:
        p10,p50,p90,p_max,p_min=[],[],[],[],[]

    #Составление двойного графика
    fig = make_subplots(rows=2, cols=1, row_heights=[0.85, 0.15], vertical_spacing=0.02)
    year_well=chart_df.groupby(step,as_index=False,observed=True)[['Скважина']].agg('count') #подсчет скважин по годам
    
    if (graph=='Веер профилей') and len(horizon)!=0:
        for i,f in enumerate(chart_df['Месторождение'].unique()):
            for j,h in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                j=j+i*10
                for k,w in enumerate(chart_df['Скважина'][(chart_df['Пласт']==h) & (chart_df['Месторождение']==f)].unique()):
                    if (k==0) and (j%10==0):
                        fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df[step][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                            mode='markers+lines',name=h,
                            marker=dict(size=5,opacity=0.6), line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                            legendgrouptitle_text=f,legendgroup=f'horizont{j}'), row=1, col=1)
                    elif (k==0):
                        fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df[step][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                            mode='markers+lines',name=h,
                            marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                            legendgroup=f'horizont{j}'), row=1, col=1)
                    else:
                        fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df[step][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                            mode='markers+lines',name=h, showlegend=False,
                            marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                            legendgroup=f'horizont{j}'), row=1, col=1)
                    fig.update_layout(legend=dict(groupclick="togglegroup"))
        fig.update_layout(legend=dict(groupclick="toggleitem"),xaxis1=dict(range=[0.75,len(p10)+0.5]))

    elif (graph=='Ящик с усами') and len(horizon)!=0:
        fig.add_trace(go.Box(
            name="Выбранные объекты <br>факт",
            q1=p90, median=p50,q3=p10, lowerfence=p_min,upperfence=p_max,
            x=np.arange(1,len(p10)+1), offsetgroup=1,
            hovertemplate=("hui: %{x:.1f}<extra></extra>")), row=1, col=1)
#==================================================ГРУППИРОВОЧНЫЕ профиля НАЧАЛО==========================================================            
    elif (graph=='По кластерам') and len(horizon)!=0:
        chart_obj_df = chart_df.pivot_table(index=step, columns=['Кластер'], values=profil, aggfunc='mean') #mean for cluster
        for clstr in chart_obj_df.columns: #перебор месторождений и пластов
            #расчет кол-во скв по годам
            year_w=chart_df[chart_df['Кластер']==clstr].groupby(step)[['Скважина']].agg('count')
            text_graph=year_w['Скважина'].apply(lambda x: f'Кластер {clstr}, число скв. {x}').to_list()

            fig.add_trace(go.Scatter(
                y=chart_obj_df[clstr], x=np.arange(1,len(chart_obj_df[clstr].dropna())+1),
                mode='markers+lines',name=f'Кластер {clstr}',
                text=text_graph, #заполнение для каждой точки
                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                hovertemplate="%{text}<br>"+{'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)

    elif (graph=='По месторождениям') and len(horizon)!=0:
        chart_obj_df = chart_df.pivot_table(index=step, columns=['Кластер','Месторождение'], values=profil, aggfunc='mean') #mean for fields

        for clstr,f in chart_obj_df.columns: #перебор месторождений и пластов
            year_w=chart_df[(chart_df['Кластер']==clstr)&(chart_df['Месторождение']==f)].groupby(step)[['Скважина']].agg('count')
            text_graph=year_w['Скважина'].apply(lambda x: f'Кластер {clstr}, {f}, число скв. {x}').to_list()
            fig.add_trace(go.Scatter(
                y=chart_obj_df[clstr][f], x=np.arange(1,len(chart_obj_df[clstr][f].dropna())+1),
                mode='markers+lines',name=f'Кластер {clstr}, {f}',
                text=text_graph, #заполнение для каждой точки
                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                hovertemplate="%{text}<br>"+{'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), 
                row=1, col=1)

    elif (graph=='По пластам') and len(horizon)!=0:
        chart_obj_df = chart_df.pivot_table(index=step, columns=['Месторождение','Пласт'], values=profil, aggfunc='mean') #mean for horizon
        #chart_df.groupby(['Годы', 'Пласт'])['Нефть, тыс т'].agg('mean').unstack()

        for f,h in chart_obj_df.columns: #перебор месторождений и пластов
            year_w=chart_df[(chart_df['Месторождение']==f)&(chart_df['Пласт']==h)].groupby(step)[['Скважина']].agg('count')
            text_graph=year_w['Скважина'].apply(lambda x: f'{f}, {h}, число скв. {x}').to_list()
            fig.add_trace(go.Scatter(
                y=chart_obj_df[f][h], x=np.arange(1,len(chart_obj_df[f][h].dropna())+1),
                mode='markers+lines',name=f'{f}, {h}',
                text=text_graph, #заполнение для каждой точки
                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                hovertemplate="%{text}<br>"+{'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)
#==================================================ГРУППИРОВОЧНЫЕ профиля Конец==========================================================            
#добавляем перцентили для группировочных
    if graph in ['По кластерам','По месторождениям','По пластам']:
        p10_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 90),axis=1) #дроп для отсева nan в строке(axis=1)
        p50_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 50),axis=1)
        p90_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 10),axis=1)

        fig.add_trace(go.Scatter(x=np.arange(1,len(p10_grup)+1),mode="lines+markers", y=p10_grup,marker_symbol='0', marker_size=12,name='Факт P10',line=dict(width=5,color='mediumseagreen'),
                      hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",
                      legendgrouptitle_text='Персентили факт',legendgroup=f'Персентили факт'), row=1, col=1)
        fig.add_trace(go.Scatter(x=np.arange(1,len(p50_grup)+1),mode="lines+markers", y=p50_grup,marker_symbol='0', marker_size=12,name='Факт P50',line=dict(width=5,color='yellow'),
                      hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",
                      legendgroup=f'Персентили факт'), row=1, col=1)
        fig.add_trace(go.Scatter(x=np.arange(1,len(p90_grup)+1),mode="lines+markers", y=p90_grup,marker_symbol='0', marker_size=12,name='Факт P90',line=dict(width=5,color='red'),
                      hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",
                      legendgroup=f'Персентили факт'), row=1, col=1)
        fig.update_layout(xaxis1=dict(range=[0.75,len(p10_grup)+0.5]))

#дбавляем общие перцентили только для ящика и веера==================================================================
    elif graph in ['Веер профилей', 'Ящик с усами']:
        fig.add_trace(go.Scatter(x=np.arange(1,len(p10)+1),mode="lines+markers", y=p10,marker_symbol='0', marker_size=12,name='Факт P10',line=dict(width=5,color='mediumseagreen'),
                      hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",
                      legendgrouptitle_text='Персентили факт',legendgroup=f'Персентили факт'), row=1, col=1)
        fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1),mode="lines+markers", y=p50,marker_symbol='0', marker_size=12,name='Факт P50',line=dict(width=5,color='yellow'),
                      hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
        fig.add_trace(go.Scatter(x=np.arange(1,len(p90)+1),mode="lines+markers", y=p90,marker_symbol='0', marker_size=12,name='Факт P90',line=dict(width=5,color='red'),
                      hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
    
    #fig.update_layout(legend=dict(groupclick="togglegroup"))
    #----------------------Использование даннных прогноза ИИ----------------------------------------------===================================================================================
    if (ai_filename is not None) and (horizon_ai is not None): 
        data=json.loads(ai_viborka)
        ai_forecast=make_viborka_df(read_file(ai_filename,'lite'),data,step) #открываем файл из кэша и сразу фильтруем в функции
        
        p10_ai=get_percentile(ai_forecast,profil,[lambda x: np.percentile(x, 90)],step)
        p50_ai=get_percentile(ai_forecast,profil,[lambda x: np.percentile(x, 50)],step)
        p90_ai=get_percentile(ai_forecast,profil,[lambda x: np.percentile(x, 10)],step)

        if graph=='Веер профилей':
            for i,f in enumerate(ai_forecast['Месторождение'].unique()):
                for j,h in enumerate(ai_forecast['Пласт'][ai_forecast['Месторождение']==f].unique()):
                    j=j+i*10
                    for k,w in enumerate(ai_forecast['Скважина'][(ai_forecast['Пласт']==h) & (ai_forecast['Месторождение']==f)].unique()):
                        if (k==0) and (j%10==0):
                            fig.add_trace(go.Scatter(y=ai_forecast[profil][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast[step][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6), line=dict(width=0.5,color='black'),legendgrouptitle_text=f"{f} прогноз ИИ",
                                        legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                        elif (k==0):
                            fig.add_trace(go.Scatter(y=ai_forecast[profil][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast[step][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=0.5,color='black'),
                                        legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                        else:
                            fig.add_trace(go.Scatter(y=ai_forecast[profil][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast[step][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                        mode='markers+lines',name=h, showlegend=False,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=0.5,color='black'),
                                        legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            
                        fig.update_layout(legend=dict(groupclick="togglegroup"),xaxis1=dict(range=[0.75,len(p10)+0.5]))
            fig.add_trace(go.Scatter(x=np.arange(1,len(p10_ai)+1),mode="lines+markers", y=p10_ai,marker_symbol='x', marker_size=10,name='Прогноз ИИ P10',
                    line=dict(width=1,color='black',dash='dash'),
                    hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"))
            fig.add_trace(go.Scatter(x=np.arange(1,len(p50_ai)+1),mode="lines+markers", y=p50_ai,marker_symbol='x', marker_size=10,name='Прогноз ИИ P50',
                    line=dict(width=1,color='black',dash='dash'),
                    hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"))
            fig.add_trace(go.Scatter(x=np.arange(1,len(p90_ai)+1),mode="lines+markers", y=p90_ai,marker_symbol='x', marker_size=10,name='Прогноз ИИ P90',
                    line=dict(width=1,color='black',dash='dash'),
                    hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"))        
        elif graph=='Ящик с усами':
            p_max_ai=get_percentile(ai_forecast,profil,'max',step)
            p_min_ai=get_percentile(ai_forecast,profil,'min',step)          
        
            fig.add_trace(go.Box(name="Выбранные объекты <br>(прогноз ИИ)",q1=p90_ai, median=p50_ai,q3=p10_ai, lowerfence=p_min_ai,upperfence=p_max_ai,
                x=np.arange(1,len(p10_ai)+1)+0.5,offsetgroup=1,
                hovertemplate=("Max: %{y:.1f}<br>"+
                               "P10: %{q3:.1f}<br>"+
                               "P50: %{median:.1f}<br>"+
                               "P90: %{q1:.1f}<br>"+
                               "Min: %{min:.1f}<extra></extra>")),row=1,col=1)
    #--------------------------------------------------------------------------------------------===============================================================================================
    # Нижняя гистограмма
    fig.add_trace(go.Bar(x=year_well[step], y=year_well['Скважина'], name='Количество скважин', marker=dict(color='orange'),
                         hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+"Кол-во скв всего: %{y:.0f} шт<extra></extra>", offsetgroup=1,
                         text=year_well['Скважина'],textposition='auto'), row=2, col=1)
    
    fig.update_layout(
        height=700, width=800, 
        title_text=f'Сценарий 1-Обычные профиля, {label_dict[profil][0]}', 
        showlegend=True,
        yaxis1=dict(title=f"{label_dict[profil][0]}, {label_dict[profil][1]}"), # в год/месяц
        yaxis2=dict(title="Кол-во скважин"),
        xaxis1=dict(showticklabels=False), #убрать тики оси х верхнего грф  
        xaxis2=dict(title=step,tickmode='array',tickvals=year_well[step])) #название в зависимости от шага
   
    return fig
#------------------------------------------ГРАФИК УДЕЛЬНЫХ ПРОФИЛЕЙ-------------------------------------------------------------------

#@app.callback(
#    Output('udeln profils', 'figure'),
#    [State('upload fact data','filename'),
#     State('upload ai data', 'filename')],
#     
#    [Input('field-selector', 'value'),
#     Input('plast-selector', 'value'),
#     Input('lgs-slider','value'),
#     Input('nfrac-slider','value'),
#     Input('mprop-slider','value'),
#
#     Input('profil-selector','value'),
#     Input('profil-rb', 'value'),
#
#     Input('field-selector-ai', 'value'),
#     Input('plast-selector-ai', 'value'),
#
#     Input('udeln perm', 'n_clicks'),
#     Input('udeln nfrac','n_clicks'),
#     Input('udeln hoil', 'n_clicks'),
#     Input('udeln heff', 'n_clicks'),
#     Input('udeln mprop','n_clicks'),
#     Input('udeln 1/mu', 'n_clicks'),
#     
#     Input('deviat-check','value'),
#     Input('deviat-slider','value')])
@app.callback(
    Output('udeln profils', 'figure'),
    [State('upload fact data','filename'),
     State('upload ai data', 'filename')],
     
    [Input('fact_data-slide-filtering','data'), #Подгрузка набора фильтров для факт выборки-тригер
     Input('ai_data-slide-filtering','data'),   #Подгрузка набора фильтров для прогн выборки-тригер
     
     Input('plast-selector', 'value'), #для тригера
     Input('plast-selector-ai', 'value'), #для тригера

     Input('profil-selector','value'),
     Input('step-rb', 'value'),
     Input('profil-rb', 'value'),

     Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac','n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff', 'n_clicks'),
     Input('udeln mprop','n_clicks'),
     Input('udeln 1/mu', 'n_clicks'),
     
     Input('deviat-check','value'),
     Input('deviat-slider','value')])
def q_profils_udeln(fact_filename,ai_filename,fact_viborka,ai_viborka,
                    horizon,horizon_ai,profil,step,graph,
                    click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu,deviat_chek,percent):
    if (fact_filename is None) or (horizon is None):
        return go.Figure()
    
    data=json.loads(fact_viborka)
    chart_df=make_viborka_df(read_file(fact_filename,'lite'),
                             data,
                             step) #открываем файл из кэша и сразу применяем фильтры из словаря в функции make_viborka_df()
    if step=='Месяцы':
        chart_df=chart_df[chart_df['Месяцы'].isin(range(1,37))]
    #if deviat_chek:
    #    mean_values = chart_df[data_columns].mean() # Вычислить среднее значение для каждого столбца
    #    lower_bound = mean_values * (1-percent/100)
    #    upper_bound = mean_values * (1+percent/100)
    #    chart_df = chart_df[chart_df[data_columns].apply(lambda x: x.between(lower_bound[x.name], upper_bound[x.name])).all(axis=1)] # Отфильтровать df с помощью .between
    #
    colors = px.colors.qualitative.Plotly[:len(chart_df['Пласт'].unique())]
    color_map = dict(zip(chart_df['Пласт'].unique(), colors))
    chart_df['Цвет пласт'] = chart_df['Пласт'].map(color_map)

    if profil not in ['ГФ, м3/т','Обв, %','Темп падения Qн','Темп падения Qж']: #профиля в списке не нормируем 
    #_____________________________________________________
        ctx = callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        if trigger_id:
            button_states = [click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu]
            selected_buttons = [i for i, state in enumerate(button_states, start=1) if state % 2 != 0]
            if selected_buttons:
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                'Средняя эффективная мощность коллектора (ГИС)','Масса проппанта на стадию','1/Вязкость'] 
                divisor = chart_df[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                chart_df[profil]=chart_df[profil] / divisor
    #_____________________________________________________
        if (horizon is not None) and len(chart_df)!=0: #расчет средних отнормированных
            p10=get_percentile(chart_df,profil,[lambda x: np.percentile(x, 90)],step)
            p50=get_percentile(chart_df,profil,[lambda x: np.percentile(x, 50)],step)
            p90=get_percentile(chart_df,profil,[lambda x: np.percentile(x, 10)],step)

            p_max=get_percentile(chart_df,profil,'max',step)   
            p_min=get_percentile(chart_df,profil,'min',step)
        else:
            p10,p50,p90,p_max,p_min=[],[],[],[],[]
        #Составление двойного графика
        fig = make_subplots(rows=2, cols=1, row_heights=[0.85, 0.15], vertical_spacing=0.02)
        year_well=chart_df.groupby(step,as_index=False,observed=True)[['Скважина']].agg('count') #подсчет скважин по годам

        if (graph=='Веер профилей') and len(horizon)!=0:
            for i,f in enumerate(chart_df['Месторождение'].unique()):
                for j,h in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    j=j+i*10
                    for k,w in enumerate(chart_df['Скважина'][(chart_df['Пласт']==h) & (chart_df['Месторождение']==f)].unique()):
                        if (k==0) and (j%10==0):
                            fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df[step][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6), line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgrouptitle_text=f,legendgroup=f'horizont{j}'), row=1, col=1)
                        elif (k==0):
                            fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df[step][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'), row=1, col=1)
                        else:
                            fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df[step][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h, showlegend=False,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'), row=1, col=1)
                            
                        fig.update_layout(legend=dict(groupclick="togglegroup"))
            fig.update_layout(legend=dict(groupclick="toggleitem"),xaxis1=dict(range=[0.75,len(p10)+0.5]))

        elif (graph=='Ящик с усами')and len(horizon)!=0:      
            fig.add_trace(go.Box(name="Выбранные объекты <br> удельн. факт",q1=p90, median=p50,q3=p10, lowerfence=p_min,upperfence=p_max,
                                 x=np.arange(1,len(p10)+1)), row=1, col=1) 
#==================================================ГРУППИРОВОЧНЫЕ профиля НАЧАЛО==========================================================            
        elif (graph=='По кластерам') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index=step, columns=['Кластер'], values=profil, aggfunc='mean') #mean for cluster
            for clstr in chart_obj_df.columns: #перебор месторождений и пластов
                #расчет кол-во скв по годам
                year_w=chart_df[chart_df['Кластер']==clstr].groupby(step)[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'Кластер {clstr}, число скв. {x}').to_list()

                fig.add_trace(go.Scatter(
                    y=chart_obj_df[clstr], x=np.arange(1,len(chart_obj_df[clstr].dropna())+1),
                    mode='markers+lines',name=f'Кластер {clstr}',
                    text=text_graph, #заполнение для каждой точки
                    marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                    hovertemplate="%{text}<br>"+{'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)

        elif (graph=='По месторождениям') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index=step, columns=['Кластер','Месторождение'], values=profil, aggfunc='mean') #mean for fields

            for clstr,f in chart_obj_df.columns: #перебор месторождений и пластов
                year_w=chart_df[(chart_df['Кластер']==clstr)&(chart_df['Месторождение']==f)].groupby(step)[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'Кластер {clstr}, {f}, число скв. {x}').to_list()
                fig.add_trace(go.Scatter(
                    y=chart_obj_df[clstr][f], x=np.arange(1,len(chart_obj_df[clstr][f].dropna())+1),
                    mode='markers+lines',name=f'Кластер {clstr}, {f}',
                    text=text_graph, #заполнение для каждой точки
                    marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                    hovertemplate="%{text}<br>"+{'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)

        elif (graph=='По пластам') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index=step, columns=['Месторождение','Пласт'], values=profil, aggfunc='mean') #mean for horizon
            #chart_df.groupby(['Годы', 'Пласт'])['Нефть, тыс т'].agg('mean').unstack()

            for f,h in chart_obj_df.columns: #перебор месторождений и пластов
                year_w=chart_df[(chart_df['Месторождение']==f)&(chart_df['Пласт']==h)].groupby(step)[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'{f}, {h}, число скв. {x}').to_list()
                fig.add_trace(go.Scatter(
                    y=chart_obj_df[f][h], x=np.arange(1,len(chart_obj_df[f][h].dropna())+1),
                    mode='markers+lines',name=f'{f}, {h}',
                    text=text_graph, #заполнение для каждой точки
                    marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                    hovertemplate="%{text}<br>"+{'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)
#==================================================ГРУППИРОВОЧНЫЕ профиля Конец==========================================================            
#добавляем перцентили для группировочных
        if graph in ['По кластерам','По месторождениям','По пластам']:
            p10_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 90),axis=1) #дроп для отсева nan в строке(axis=1)
            p50_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 50),axis=1)
            p90_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 10),axis=1)

            fig.add_trace(go.Scatter(x=np.arange(1,len(p10_grup)+1),mode="lines+markers", y=p10_grup,marker_symbol='0', marker_size=12,name='Удельн. факт P10',line=dict(width=5,color='mediumseagreen'),
                        hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",
                        legendgrouptitle_text='Персентили факт',legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p50_grup)+1),mode="lines+markers", y=p50_grup,marker_symbol='0', marker_size=12,name='Удельн. факт P50',line=dict(width=5,color='yellow'),
                        hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p90_grup)+1),mode="lines+markers", y=p90_grup,marker_symbol='0', marker_size=12,name='Удельн. факт P90',line=dict(width=5,color='red'),
                        hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.update_layout(xaxis1=dict(range=[0.75,len(p10_grup)+0.5]))
#дбавляем общие перцентили только для ящика и веера==================================================================
        elif graph in ['Веер профилей', 'Ящик с усами']:
            fig.add_trace(go.Scatter(x=np.arange(1,len(p10)+1),mode="lines+markers", y=p10,marker_symbol='0', marker_size=12,name='Удельн. факт P10',line=dict(width=5,color='mediumseagreen'),
                          hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",
                          legendgrouptitle_text='Персентили факт',legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1),mode="lines+markers", y=p50,marker_symbol='0', marker_size=12,name='Удельн. факт P50',line=dict(width=5,color='yellow'),
                          hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p90)+1),mode="lines+markers", y=p90,marker_symbol='0', marker_size=12,name='Удельн. факт P90',line=dict(width=5,color='red'),
                          hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
        
            #fig.update_layout(legend=dict(groupclick="togglegroup"))
        #----------------------Использование даннных прогноза ИИ--------------------------------
        if (ai_filename is not None) and (horizon_ai is not None):
            ai_forecast = make_viborka_df(read_file(ai_filename,'lite'),data,step) #открываем файл из кэша и сразу фильтруем в функции

            #if selected_buttons: #если не пустые
            #    divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
            #                    'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
            #                    'Средняя эффективная мощность коллектора (ГИС)','Масса проппанта на стадию','1/Вязкость'] 
            #    divisor_ai = ai_forecast[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
            #    ai_forecast[profil]=ai_forecast[profil] / divisor_ai #делаем удельные

            p10_ai=get_percentile(ai_forecast,profil,[lambda x: np.percentile(x, 90)],step)
            p50_ai=get_percentile(ai_forecast,profil,[lambda x: np.percentile(x, 50)],step)
            p90_ai=get_percentile(ai_forecast,profil,[lambda x: np.percentile(x, 10)],step)

            if graph=='Веер профилей':
                for i,f in enumerate(ai_forecast['Месторождение'].unique()):
                    for j,h in enumerate(ai_forecast['Пласт'][ai_forecast['Месторождение']==f].unique()):
                        j=j+i*10
                        for k,w in enumerate(ai_forecast['Скважина'][(ai_forecast['Пласт']==h) & (ai_forecast['Месторождение']==f)].unique()):
                            if (k==0) and (j%10==0):
                                fig.add_trace(go.Scatter(y=ai_forecast[profil][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast[step][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h,
                                            marker=dict(size=5,opacity=0.6), line=dict(width=0.5,color='black'),legendgrouptitle_text=f"{f} удельн. прогноз ИИ",
                                            legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            elif (k==0):
                                fig.add_trace(go.Scatter(y=ai_forecast[profil][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast[step][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h,
                                            marker=dict(size=5,opacity=0.6),line=dict(width=0.5,color='black'),
                                            legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            else:
                                fig.add_trace(go.Scatter(y=ai_forecast[profil][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast[step][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h, showlegend=False,
                                            marker=dict(size=5,opacity=0.6),line=dict(width=0.5,color='black'),
                                            legendgroup=f'horizont{j} прогноз ИИ'))
                            fig.update_layout(legend=dict(groupclick="togglegroup"), row=1, col=1)
    
                fig.add_trace(go.Scatter(x=np.arange(1,len(p50_ai)+1),mode="lines+markers", y=p50_ai,marker_symbol='x', marker_size=10,name='Удельн. прогноз ИИ P50',line=dict(width=1,color='black',dash='dash'),
                    hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"))       
            elif graph=='Ящик с усами':
                p_max_ai=get_percentile(ai_forecast,profil,'max',step)
                p_min_ai=get_percentile(ai_forecast,profil,'min',step)      

                fig.add_trace(go.Box(name="Выбранные объекты <br>(прогноз ИИ)",q1=p90_ai, median=p50_ai,q3=p10_ai, lowerfence=p_min_ai,upperfence=p_max_ai,
                                     x=np.arange(1,len(p10_ai)+1)+0.5),row=1,col=1)

    #-------------------------------------------------------------------------------------------
        # Нижняя гистограмма
        fig.add_trace(go.Bar(x=year_well[step], y=year_well['Скважина'], name='Количество скважин', marker=dict(color='orange'),
                             hovertemplate={'Годы':"Год:",'Месяцы':"Месяц:"}[step]+"%{x:.0f}<br>"+"Кол-во скв всего: %{y:.0f} шт<extra></extra>", offsetgroup=1,
                             text=year_well['Скважина'],textposition='auto'), row=2, col=1)

        fig.update_layout(
            height=700, width=800, 
            title_text=f'Сценарий 1-Удельные профиля, {label_dict[profil][0]+"".join([norm_mult[i] for i in selected_buttons])}', 
            showlegend=True,
            yaxis1=dict(title=f"{label_dict[profil][0]+"".join([norm_mult[i] for i in selected_buttons])}"),
            yaxis2=dict(title="Кол-во скважин"),
            xaxis1=dict(showticklabels=False), #убрать тики оси х верхнего грф
            xaxis2=dict(title=step,tickmode='array',tickvals=year_well[step])) 
        
        return fig
    else:
        return make_subplots(rows=2, cols=1, row_heights=[0.85, 0.15], vertical_spacing=0.02)


#------------------------------------------ГРАФИК ДИСКОНТИРОВАННЫХ ПРОФИЛЕЙ-------------------------------------------------------------------
new_profil={'Накопленная нефть, тыс т':'Нефть, тыс т',
            'Накопленная жидкость, тыс т':'Жидкость, тыс т',
            'Накопленная жидкость, тыс м3':'Жидкость, тыс м3',
            'Накопленный ПНГ':'ПНГ, млн м3'}

@app.callback(
    Output('discont profils', 'figure'),
    [State('upload fact data','filename'),
     State('upload ai data', 'filename')],

    [Input('fact_data-slide-filtering','data'), #Подгрузка набора фильтров для факт выборки-тригер
     Input('ai_data-slide-filtering','data'),   #Подгрузка набора фильтров для прогн выборки-тригер

     Input('plast-selector', 'value'),
     Input('plast-selector-ai', 'value'),#ввод значения коэф дисконтирования,

     Input('profil-selector', 'value'),
     Input('step-rb','value'),
     Input('profil-rb','value'),
     Input('coef discont', 'value'), #коэф диск
     Input('deviat-check','value'),
     Input('deviat-slider','value')]) 

def q_discont(fact_filename,ai_filename,fact_viborka,ai_viborka,horizon,horizon_ai,profil,step,graph,coef_discont,deviat_chek,percent):
    if (fact_filename is None) or (horizon is None) :
        return go.Figure()
    
    data=json.loads(fact_viborka)
    step='Годы' # ДДН только по годам
    chart_df=make_viborka_df(read_file(fact_filename,'lite'), data, step) #открываем файл из кэша и сразу применяем фильтры из словаря в функции make_viborka_df()
            
    if ('Накоп' in profil):
        profil1=new_profil[profil] #перевод из накоп в обычную
        #ниже делает сначала диск, а потои переводит в накоп. (это правильно!) 
        chart_df[f'{profil1} дисконтирование']=chart_df[profil1]*((1+coef_discont/100)**chart_df['Годы'])**(-1)
        chart_df[f'{profil1} дисконтирование']=chart_df.groupby(['Месторождение','Скважина'])[f'{profil1} дисконтирование'].cumsum()
    else:
        profil1=profil
        chart_df[f'{profil1} дисконтирование']=chart_df[profil1]*((1+coef_discont/100)**chart_df['Годы'])**(-1)

    if deviat_chek:
        mean_values = chart_df[data_columns].mean() # Вычислить среднее значение для каждого столбца
        lower_bound = mean_values * (1-percent/100)
        upper_bound = mean_values * (1+percent/100)
        chart_df = chart_df[chart_df[data_columns].apply(lambda x: x.between(lower_bound[x.name], upper_bound[x.name])).all(axis=1)] # Отфильтровать df с помощью .between
    #
    colors = px.colors.qualitative.Plotly[:len(chart_df['Пласт'].unique())]
    color_map = dict(zip(chart_df['Пласт'].unique(), colors))
    chart_df['Цвет пласт'] = chart_df['Пласт'].map(color_map)

    if profil not in ['ГФ, м3/т','Обв, %','Темп падения Qн','Темп падения Qж'] :
        if len(horizon)!=0:
            p10=get_percentile(chart_df,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 90)],step)
            p50=get_percentile(chart_df,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 50)],step)
            p90=get_percentile(chart_df,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 10)],step)
            p_max=get_percentile(chart_df,f'{profil1} дисконтирование','max',step)   
            p_min=get_percentile(chart_df,f'{profil1} дисконтирование','min',step)      
        else: 
            p10,p50,p90,p_min,p_max=[],[],[],[],[]
        #Составление двойного графика
        fig = make_subplots(rows=2, cols=1, row_heights=[0.85, 0.15], vertical_spacing=0.02)
        year_well=chart_df.groupby('Годы',as_index=False,observed=True)[['Скважина']].agg('count') #подсчет скважин по годам

        if (graph=='Веер профилей') and len(horizon)!=0:
            for i,f in enumerate(chart_df['Месторождение'].unique()):
                for j,h in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    j=j+i*10
                    for k,w in enumerate(chart_df['Скважина'][(chart_df['Пласт']==h) & (chart_df['Месторождение']==f)].unique()):
                        if (k==0) and (j%10==0):
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil1} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6), line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgrouptitle_text=f'Диск. {f}',legendgroup=f'horizont{j}'), row=1, col=1)
                        elif (k==0):
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil1} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'), row=1, col=1)
                        else:
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil1} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h, showlegend=False,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'), row=1, col=1)
                        fig.update_layout(legend=dict(groupclick="togglegroup"))
        elif (graph=='Ящик с усами') and len(horizon)!=0:            
            fig.add_trace(go.Box(name="Выбранные объекты<br>диск. факт",q1=p90, median=p50,q3=p10, lowerfence=p_min,upperfence=p_max,
                                 x=np.arange(1,len(p10)+1)), row=1, col=1)
            
#==================================================ГРУППИРОВОЧНЫЕ профиля НАЧАЛО==========================================================            
        elif (graph=='По кластерам') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index='Годы', columns=['Кластер'], values=f'{profil1} дисконтирование', aggfunc='mean') #mean for cluster
            for clstr in chart_obj_df.columns: #перебор месторождений и пластов
                #расчет кол-во скв по годам
                year_w=chart_df[chart_df['Кластер']==clstr].groupby('Годы')[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'Кластер {clstr}, число скв. {x}').to_list()

                fig.add_trace(go.Scatter(
                                y=chart_obj_df[clstr], x=np.arange(1,len(chart_obj_df[clstr].dropna())+1),
                                mode='markers+lines',name=f'Кластер {clstr}',
                                text=text_graph, #заполнение для каждой точки
                                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                                hovertemplate="%{text}<br>Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)

        elif (graph=='По месторождениям') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index='Годы', columns=['Кластер','Месторождение'], values=f'{profil1} дисконтирование', aggfunc='mean') #mean for fields

            for clstr,f in chart_obj_df.columns: #перебор месторождений и пластов
                year_w=chart_df[(chart_df['Кластер']==clstr)&(chart_df['Месторождение']==f)].groupby('Годы')[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'Кластер {clstr}, {f}, число скв. {x}').to_list()
                fig.add_trace(go.Scatter(
                                y=chart_obj_df[clstr][f], x=np.arange(1,len(chart_obj_df[clstr][f].dropna())+1),
                                mode='markers+lines',name=f'Кластер {clstr}, {f}',
                                text=text_graph, #заполнение для каждой точки
                                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                                hovertemplate="%{text}<br>Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)

        elif (graph=='По пластам') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index='Годы', columns=['Месторождение','Пласт'], values=f'{profil1} дисконтирование', aggfunc='mean') #mean for horizon
            #chart_df.groupby(['Годы', 'Пласт'])['Нефть, тыс т'].agg('mean').unstack()

            for f,h in chart_obj_df.columns: #перебор месторождений и пластов
                year_w=chart_df[(chart_df['Месторождение']==f)&(chart_df['Пласт']==h)].groupby('Годы')[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'{f}, {h}, число скв. {x}').to_list()
                fig.add_trace(go.Scatter(
                                y=chart_obj_df[f][h], x=np.arange(1,len(chart_obj_df[f][h].dropna())+1),
                                mode='markers+lines',name=f'{f}, {h}',
                                text=text_graph, #заполнение для каждой точки
                                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                                hovertemplate="%{text}<br>Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)
            
#==================================================ГРУППИРОВОЧНЫЕ профиля Конец==========================================================            
#добавляем перцентили для группировочных
        if graph in ['По кластерам','По месторождениям','По пластам']:
            p10_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 90),axis=1) #дроп для отсева nan в строке(axis=1)
            p50_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 50),axis=1)
            p90_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 10),axis=1)

            fig.add_trace(go.Scatter(x=np.arange(1,len(p10_grup)+1),mode="lines+markers", y=p10_grup,marker_symbol='0', marker_size=12,name='Диск. факт P10',line=dict(width=5,color='mediumseagreen'),
                          hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",
                          legendgrouptitle_text='Персентили факт',legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p50_grup)+1),mode="lines+markers", y=p50_grup,marker_symbol='0', marker_size=12,name='Диск. факт P50',line=dict(width=5,color='yellow'),
                          hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p90_grup)+1),mode="lines+markers", y=p90_grup,marker_symbol='0', marker_size=12,name='Диск. факт P90',line=dict(width=5,color='red'),
                          hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.update_layout(xaxis1=dict(range=[0.75,len(p10_grup)+0.5]))
#дбавляем общие перцентили только для ящика и веера==================================================================
        elif graph in ['Веер профилей', 'Ящик с усами']:
            fig.add_trace(go.Scatter(x=np.arange(1,len(p10)+1),mode="lines+markers", y=p10,marker_symbol='0', marker_size=12,name='Диск. факт P10',line=dict(width=5,color='mediumseagreen'),
                          hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",
                          legendgrouptitle_text='Персентили факт',legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1),mode="lines+markers", y=p50,marker_symbol='0', marker_size=12,name='Диск. факт P50',line=dict(width=5,color='yellow'),
                          hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p90)+1),mode="lines+markers", y=p90,marker_symbol='0', marker_size=12,name='Диск. факт P90',line=dict(width=5,color='red'),
                          hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f}<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)

            fig.update_layout(legend=dict(groupclick="togglegroup"))

    #----------------------Использование даннных прогноза ИИ----------------------------------------------======================================================================================
        if (ai_filename is not None) and (horizon_ai is not None):
            data=json.loads(ai_viborka)
            ai_forecast=make_viborka_df(read_file(ai_filename,'lite'),data,step) #открываем файл из кэша и сразу фильтруем в функции

            if ('Накоп' in profil):
                #ниже делает сначала диск, а потои переводит в накоп. (это правильно!)
                profil1=new_profil[profil] 
                ai_forecast[f'{profil1} дисконтирование']=ai_forecast[profil1]*((1+coef_discont/100)**ai_forecast['Годы'])**(-1)
                ai_forecast[f'{profil1} дисконтирование']=ai_forecast.groupby(['Месторождение','Скважина'])[f'{new_profil[profil]} дисконтирование'].cumsum()
            else:
                profil1=profil
                ai_forecast[f'{profil} дисконтирование']=ai_forecast[profil]*((1+coef_discont/100)**ai_forecast['Годы'])**(-1)

            p10_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 90)],step)
            p50_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 50)],step)
            p90_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 10)],step)

            if graph=='Веер профилей':
                for i,f in enumerate(ai_forecast['Месторождение'].unique()):
                    for j,h in enumerate(ai_forecast['Пласт'][ai_forecast['Месторождение']==f].unique()):
                        j=j+i*10
                        for k,w in enumerate(ai_forecast['Скважина'][(ai_forecast['Пласт']==h) & (ai_forecast['Месторождение']==f)].unique()):
                            if (k==0) and (j%10==0):
                                fig.add_trace(go.Scatter(y=ai_forecast[f'{profil1} дисконтирование'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast['Годы'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h,
                                            marker=dict(size=5,opacity=0.6), line=dict(width=0.5,color='black'),legendgrouptitle_text=f"{f}  диск. прогноз ИИ",
                                            legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            elif (k==0):
                                fig.add_trace(go.Scatter(y=ai_forecast[f'{profil1} дисконтирование'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast['Годы'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h,
                                            marker=dict(size=5,opacity=0.6),line=dict(width=0.5,color='black'),
                                            legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            else:
                                fig.add_trace(go.Scatter(y=ai_forecast[f'{profil1} дисконтирование'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast['Годы'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h, showlegend=False,
                                            marker=dict(size=5,opacity=0.6),line=dict(width=0.5,color='black'),
                                            legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            fig.update_layout(legend=dict(groupclick="togglegroup"))

                fig.add_trace(go.Scatter(x=np.arange(1,len(p50_ai)+1),mode="lines+markers", y=p50_ai,marker_symbol='x', marker_size=10,name='Прогноз ИИ P50',line=dict(width=1,color='black',dash='dash'),
                        hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"))
            elif graph=='Ящик с усами':
                p_max_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование','max',step)
                p_min_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование','min',step)                       

                fig.add_trace(go.Box(name="Выбранные объекты <br>(Диск. прогноз ИИ)",q1=p90_ai, median=p50_ai,q3=p10_ai, lowerfence=p_min_ai,upperfence=p_max_ai,
                                     x=np.arange(1,len(p10_ai)+1)+0.5), row=1, col=1)       
    #--------------------------------------------------------------------------------------------===============================================================================================
        # Нижняя гистограмма
        fig.add_trace(go.Bar(x=year_well['Годы'], y=year_well['Скважина'], name='Количество скважин', marker=dict(color='orange'),
                         hovertemplate="Год: %{x:.0f}<br>"+"Кол-во скв всего: %{y:.0f} шт<extra></extra>", offsetgroup=1,
                         text=year_well['Скважина'],textposition='auto'), row=2, col=1)
        
        fig.update_layout(
            height=700, width=800, 
            title_text=f'Дисконтированные профиля, ставка {coef_discont}%', 
            showlegend=True,
            yaxis1=dict(title=f"{label_dict[profil][0]} в год, {label_dict[profil][1]}"),
            yaxis2=dict(title="Кол-во скважин"),
            xaxis1=dict(showticklabels=False), #убрать тики оси х верхнего грф
            xaxis2=dict(title='Годы',tickmode='array',tickvals=year_well['Годы'])) 

        return fig
    else:
        return make_subplots(rows=2, cols=1, row_heights=[0.85, 0.15], vertical_spacing=0.02)
    
#'''
#-------------------------------------------ГРАФИК Удельных ДИСКОНТИРОВАННЫХ ПРОФИЛЕЙ----------------------------------------------------------
@app.callback(
    Output('udeln discont profils', 'figure'),
    [State('upload fact data', 'filename'),
     State('upload ai data', 'filename')],

    [Input('fact_data-slide-filtering','data'), #Подгрузка набора фильтров для факт выборки-тригер
     Input('ai_data-slide-filtering','data'),   #Подгрузка набора фильтров для прогн выборки-тригер
     Input('plast-selector', 'value'),
     Input('plast-selector-ai', 'value'),

     Input('profil-selector', 'value'),
     Input('step-rb','value'),
     Input('profil-rb','value'),
     Input('coef discont', 'value'), #ввод значения коэф дисконтировани     

     Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac', 'n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff', 'n_clicks'),
     Input('udeln mprop', 'n_clicks'),
     Input('udeln 1/mu', 'n_clicks'),
     Input('deviat-check','value'),
     Input('deviat-slider','value')])

#def q_discont(fact_filename,ai_filename,fact_viborka,ai_viborka,horizon,horizon_ai,profil,step,graph,coef_discont,field_ai,deviat_chek,percent):
def q_discont_udeln(fact_filename,ai_filename,fact_viborka,ai_viborka,horizon,horizon_ai,profil,step,graph,coef_discont,
                    click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu,deviat_chek,percent):
    if (fact_filename is None) or (horizon is None):
        return go.Figure()
    
    data=json.loads(fact_viborka)
    step='Годы' # ДДН только по годам
    chart_df=make_viborka_df(read_file(fact_filename,'lite'), data, step) #открываем файл из кэша и сразу применяем фильтры из словаря в функции make_viborka_df()

    if ('Накоп' in profil):
        profil1=new_profil[profil] #перевод из накоп в обычную
        #ниже делает сначала диск, а потои переводит в накоп. (это правильно!) 
        chart_df[f'{profil1} дисконтирование']=chart_df[profil1]*((1+coef_discont/100)**chart_df['Годы'])**(-1)
        chart_df[f'{profil1} дисконтирование']=chart_df.groupby(['Месторождение','Скважина'])[f'{profil1} дисконтирование'].cumsum()
    else:
        profil1=profil
        chart_df[f'{profil1} дисконтирование']=chart_df[profil1]*((1+coef_discont/100)**chart_df['Годы'])**(-1)

    if deviat_chek:
        mean_values = chart_df[data_columns].mean() # Вычислить среднее значение для каждого столбца
        lower_bound = mean_values * (1-percent/100)
        upper_bound = mean_values * (1+percent/100)
        chart_df = chart_df[chart_df[data_columns].apply(lambda x: x.between(lower_bound[x.name], upper_bound[x.name])).all(axis=1)] # Отфильтровать df с помощью .between
    #
    colors = px.colors.qualitative.Plotly[:len(chart_df['Пласт'].unique())]
    color_map = dict(zip(chart_df['Пласт'].unique(), colors))
    chart_df['Цвет пласт'] = chart_df['Пласт'].map(color_map)

    if profil not in ['ГФ, м3/т','Обв, %','Темп падения Qн','Темп падения Qж']: #профиля в списке не нормируем 
    #_____________________________________________________
        ctx = callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        if trigger_id:
            button_states = [click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu]
            selected_buttons = [i for i, state in enumerate(button_states, start=1) if state % 2 != 0]
            if selected_buttons:
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                'Средняя эффективная мощность коллектора (ГИС)','Масса проппанта на стадию','1/Вязкость'] 
                divisor = chart_df[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                chart_df[f'{profil1} дисконтирование']=chart_df[f'{profil1} дисконтирование'] / divisor

        if len(horizon)!=0:
            p10=get_percentile(chart_df,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 90)],step)
            p50=get_percentile(chart_df,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 50)],step)
            p90=get_percentile(chart_df,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 10)],step)
            p_max=get_percentile(chart_df,f'{profil1} дисконтирование','max',step)   
            p_min=get_percentile(chart_df,f'{profil1} дисконтирование','min',step) 
        else:
            p10,p50,p90,p_max,p_min=[],[],[],[],[]

        #Составление двойного графика
        fig = make_subplots(rows=2, cols=1, row_heights=[0.85, 0.15], vertical_spacing=0.02)
        year_well=chart_df.groupby('Годы',as_index=False,observed=True)[['Скважина']].agg('count') #подсчет скважин по годам

        if (graph=='Веер профилей') and len(horizon)!=0:
            for i,f in enumerate(chart_df['Месторождение'].unique()):
                for j,h in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    j=j+i*10
                    for k,w in enumerate(chart_df['Скважина'][(chart_df['Пласт']==h) & (chart_df['Месторождение']==f)].unique()):
                        if (k==0) and (j%10==0):
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil1} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6), line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgrouptitle_text=f,legendgroup=f'horizont{j}'), row=1, col=1)
                        elif (k==0):
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil1} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'), row=1, col=1)
                        else:
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil1} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h, showlegend=False,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'), row=1, col=1)
                            
                        fig.update_layout(legend=dict(groupclick="togglegroup"))
        elif (graph=='Ящик с усами') and len(horizon)!=0:
            fig.add_trace(go.Box(name="Выбранные объекты",q1=p90, median=p50,q3=p10, lowerfence=p_min,upperfence=p_max,
                                 x=np.arange(1,len(p10)+1)), row=1, col=1)

#==================================================ГРУППИРОВОЧНЫЕ профиля НАЧАЛО==========================================================            
        elif (graph=='По кластерам') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index='Годы', columns=['Кластер'], values=f'{profil1} дисконтирование', aggfunc='mean') #mean for cluster
            for clstr in chart_obj_df.columns: #перебор месторождений и пластов
                #расчет кол-во скв по годам
                year_w=chart_df[chart_df['Кластер']==clstr].groupby('Годы')[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'Кластер {clstr}, число скв. {x}').to_list()

                fig.add_trace(go.Scatter(
                                y=chart_obj_df[clstr], x=np.arange(1,len(chart_obj_df[clstr].dropna())+1),
                                mode='markers+lines',name=f'Кластер {clstr}',
                                text=text_graph, #заполнение для каждой точки
                                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                                hovertemplate="%{text}<br>Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)

        elif (graph=='По месторождениям') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index='Годы', columns=['Кластер','Месторождение'], values=f'{profil1} дисконтирование', aggfunc='mean') #mean for fields

            for clstr,f in chart_obj_df.columns: #перебор месторождений и пластов
                year_w=chart_df[(chart_df['Кластер']==clstr)&(chart_df['Месторождение']==f)].groupby('Годы')[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'Кластер {clstr}, {f}, число скв. {x}').to_list()
                fig.add_trace(go.Scatter(
                                y=chart_obj_df[clstr][f], x=np.arange(1,len(chart_obj_df[clstr][f].dropna())+1),
                                mode='markers+lines',name=f'Кластер {clstr}, {f}',
                                text=text_graph, #заполнение для каждой точки
                                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                                hovertemplate="%{text}<br>Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)

        elif (graph=='По пластам') and len(horizon)!=0:
            chart_obj_df = chart_df.pivot_table(index='Годы', columns=['Месторождение','Пласт'], values=f'{profil1} дисконтирование', aggfunc='mean') #mean for horizon
            #chart_df.groupby(['Годы', 'Пласт'])['Нефть, тыс т'].agg('mean').unstack()

            for f,h in chart_obj_df.columns: #перебор месторождений и пластов
                year_w=chart_df[(chart_df['Месторождение']==f)&(chart_df['Пласт']==h)].groupby('Годы')[['Скважина']].agg('count')
                text_graph=year_w['Скважина'].apply(lambda x: f'{f}, {h}, число скв. {x}').to_list()
                fig.add_trace(go.Scatter(
                                y=chart_obj_df[f][h], x=np.arange(1,len(chart_obj_df[f][h].dropna())+1),
                                mode='markers+lines',name=f'{f}, {h}',
                                text=text_graph, #заполнение для каждой точки
                                marker=dict(size=5,opacity=0.6), line=dict(width=2.5),
                                hovertemplate="%{text}<br>Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)
            
#==================================================ГРУППИРОВОЧНЫЕ профиля Конец==========================================================            
#добавляем перцентили для группировочных
        if graph in ['По кластерам','По месторождениям','По пластам']:
            p10_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 90),axis=1) #дроп для отсева nan в строке(axis=1)
            p50_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 50),axis=1)
            p90_grup=chart_obj_df.apply(lambda x: np.percentile(x.dropna(), 10),axis=1)

            fig.add_trace(go.Scatter(x=np.arange(1,len(p10_grup)+1),mode="lines+markers", y=p10_grup,marker_symbol='0', marker_size=12,name='Диск. удельн. фактP10',line=dict(width=5,color='mediumseagreen'),
                          hovertemplate="Год: %{x:.0f}<br>"+"Значение: %{y:.2f}<br>"+"<extra></extra>"+label_dict[profil][1]+"<extra></extra>",
                          legendgrouptitle_text='Персентили факт',legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p50_grup)+1),mode="lines+markers", y=p50_grup,marker_symbol='0', marker_size=12,name='Диск. удельн. факт P50',line=dict(width=5,color='yellow'),
                          hovertemplate="Год: %{x:.0f}<br>"+"Значение: %{y:.2f}<br>"+"<extra></extra>"+label_dict[profil][1]+"<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p90_grup)+1),mode="lines+markers", y=p90_grup,marker_symbol='0', marker_size=12,name='Диск. удельн. факт P90',line=dict(width=5,color='red'),
                          hovertemplate="Год: %{x:.0f}<br>"+"Значение: %{y:.2f}<br>"+"<extra></extra>"+label_dict[profil][1]+"<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.update_layout(xaxis1=dict(range=[0.75,len(p10_grup)+0.5]))
#дбавляем общие перцентили только для ящика и веера==================================================================
        elif graph in ['Веер профилей', 'Ящик с усами']:
            fig.add_trace(go.Scatter(x=np.arange(1,len(p10)+1),mode="lines+markers", y=p10,marker_symbol='0', marker_size=12,name='Диск. факт P10',line=dict(width=5,color='mediumseagreen'),
                          hovertemplate="Год: %{x:.0f}<br>"+"Значение: %{y:.2f}<br>"+"<extra></extra>",
                          legendgrouptitle_text='Персентили факт',legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1),mode="lines+markers", y=p50,marker_symbol='0', marker_size=12,name='Диск. факт P50',line=dict(width=5,color='yellow'),
                          hovertemplate="Год: %{x:.0f}<br>"+"Значение: %{y:.2f}<br>"+"<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1,len(p90)+1),mode="lines+markers", y=p90,marker_symbol='0', marker_size=12,name='Диск. факт P90',line=dict(width=5,color='red'),
                          hovertemplate="Год: %{x:.0f}<br>"+"Значение: %{y:.2f}<br>"+"<extra></extra>",legendgroup=f'Персентили факт'), row=1, col=1)

            fig.update_layout(legend=dict(groupclick="togglegroup"))
        #----------------------Использование даннных прогноза ИИ--------------------------------
        if (ai_filename is not None) and (horizon_ai is not None):
            data=json.loads(ai_viborka)
            ai_forecast=make_viborka_df(read_file(ai_filename,'lite'),data,step) #открываем файл из кэша и сразу фильтруем в функции

            if ('Накоп' in profil):
                #ниже делает сначала диск, а потои переводит в накоп. (это правильно!)
                profil1=new_profil[profil] 
                ai_forecast[f'{profil1} дисконтирование']=ai_forecast[profil1]*((1+coef_discont/100)**ai_forecast['Годы'])**(-1)
                ai_forecast[f'{profil1} дисконтирование']=ai_forecast.groupby(['Месторождение','Скважина'])[f'{new_profil[profil]} дисконтирование'].cumsum()
            else:
                profil1=profil
                ai_forecast[f'{profil} дисконтирование']=ai_forecast[profil]*((1+coef_discont/100)**ai_forecast['Годы'])**(-1)

            if selected_buttons: #если нажаты кнопки "удельные параметры"
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)','Средняя эффективная мощность коллектора (ГИС)',
                                'Средняя эффективная мощность коллектора (ГИС)','Масса проппанта на стадию','1/Вязкость'] 
                divisor_ai = ai_forecast[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                ai_forecast[f'{profil1} дисконтирование']=ai_forecast[f'{profil1} дисконтирование'] / divisor_ai #делаем удельные

            p10_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 90)],step)
            p50_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 50)],step)
            p90_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование',[lambda x: np.percentile(x, 10)],step)

            if graph=='Веер профилей':
                for i,f in enumerate(ai_forecast['Месторождение'].unique()):
                    for j,h in enumerate(ai_forecast['Пласт'][ai_forecast['Месторождение']==f].unique()):
                        j=j+i*10
                        for k,w in enumerate(ai_forecast['Скважина'][(ai_forecast['Пласт']==h) & (ai_forecast['Месторождение']==f)].unique()):
                            if (k==0) and (j%10==0):
                                fig.add_trace(go.Scatter(y=ai_forecast[f'{profil1} дисконтирование'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast['Годы'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h,
                                            marker=dict(size=5,opacity=0.6), line=dict(width=0.5,color='black'),legendgrouptitle_text=f"{f} удельн. прогноз ИИ",
                                            legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            elif (k==0):
                                fig.add_trace(go.Scatter(y=ai_forecast[f'{profil1} дисконтирование'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast['Годы'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h,
                                            marker=dict(size=5,opacity=0.6),line=dict(width=0.5,color='black'),
                                            legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            else:
                                fig.add_trace(go.Scatter(y=ai_forecast[f'{profil1} дисконтирование'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)],x=ai_forecast['Годы'][(ai_forecast['Скважина']==w) & (ai_forecast['Пласт']==h)], 
                                            mode='markers+lines',name=h, showlegend=False,
                                            marker=dict(size=5,opacity=0.6),line=dict(width=0.5,color='black'),
                                            legendgroup=f'horizont{j} прогноз ИИ'), row=1, col=1)
                            fig.update_layout(legend=dict(groupclick="togglegroup"))
    
                fig.add_trace(go.Scatter(x=np.arange(1,len(p50_ai)+1),mode="lines+markers", y=p50_ai,marker_symbol='x', marker_size=10,name='Удельн. прогноз ИИ P50',line=dict(width=1,color='black',dash='dash'),
                    hovertemplate="Год: %{x:.0f}<br>"+label_dict[profil][0]+": %{y:.2f} "+label_dict[profil][1]+"<extra></extra>"), row=1, col=1)       
            elif graph=='Ящик с усами':
                p_max_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование','max',step)
                p_min_ai=get_percentile(ai_forecast,f'{profil1} дисконтирование','min',step)          

                fig.add_trace(go.Box(name="Выбранные объекты <br>(Удельн. диск. прогноз ИИ)",q1=p90_ai, median=p50_ai,q3=p10_ai, lowerfence=p_min_ai,upperfence=p_max_ai,
                                     x=np.arange(1,len(p10_ai)+1)+0.5), row=1, col=1)

    #-------------------------------------------------------------------------------------------
        # Нижняя гистограмма
        fig.add_trace(go.Bar(x=year_well['Годы'], y=year_well['Скважина'], name='Количество скважин', marker=dict(color='orange'),
                             hovertemplate="Год: %{x:.0f}<br>"+"Кол-во скв всего: %{y:.0f} шт<extra></extra>", offsetgroup=1,
                             text=year_well['Скважина'],textposition='auto'), row=2, col=1)

        fig.update_layout(
            height=700, width=800, 
            title_text=f'Дисконтированные удельные профиля, ставка {coef_discont}%', 
            showlegend=True,
            yaxis1=dict(title=f"{label_dict[profil][0]+"".join([norm_mult[i] for i in selected_buttons])}"),
            yaxis2=dict(title="Кол-во скважин"),
            xaxis1=dict(showticklabels=False), #убрать тики оси х верхнего грф
            xaxis2=dict(title='Годы',tickmode='array',tickvals=year_well['Годы'])) 

        return fig
    else:
        return make_subplots(rows=2, cols=1, row_heights=[0.85, 0.15], vertical_spacing=0.02)
#'''

#-------------------------------------------СРАВНЕНИЕ ФАКТА/ГДИ И ИИ, ДОБАВЛЕНИЕ ЗНАЧЕНИЙ КРИТЕРИЕВ В ТАБЛИЦУ----------------------------------------------------------

@app.callback(
       [Output('criteria-tables','children'), #табл критериев
        Output('tables-percentile','children'), #табл подбора профиля
        Output('ei histogram','figure')],
       [State('upload fact data', 'filename'),
        State('upload ai data', 'filename')],
       [Input('field-selector', 'value'),
        Input('plast-selector', 'value'),

        Input('lgs-slider','value'),
        Input('nfrac-slider','value'),
        Input('mprop-slider','value'),

        Input('profil-selector', 'value'),
        Input('profil-choise', 'value'), # выбор профиля под перцентиль
        Input('udeln perm', 'n_clicks'),
        Input('udeln nfrac', 'n_clicks'),
        Input('udeln hoil', 'n_clicks'),
        Input('udeln heff', 'n_clicks'),
        Input('udeln mprop', 'n_clicks'),
        Input('udeln 1/mu', 'n_clicks'),

        Input('field-selector-ai', 'value'),
        Input('plast-selector-ai', 'value'),

        Input('deviat-check','value'),
        Input('deviat-slider','value'),
        Input('coef discont','value'),
        Input('num-criteria-tables','value')])
#пока реализовано для варианта 1профиль vs 1профиль
def criteria(fact_filename,ai_filename,field,horizon,
             lgs,nfrac,mprop,profil,profil_percentile,click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu,
             field_ai,horizon_ai,deviat_chek,percent,coef_discont,num_table):
    #data=[{'Критерий': None,'Значение, %':None, 'Статус': None}] 
    if (fact_filename is None) or (ai_filename is None) or (horizon is None) or (horizon_ai is None):
        return [],[], go.Figure() #data,data,data
        
    if 'Накоп' in profil:
        profil={'Накопленная нефть, тыс т':'Нефть, тыс т',
                'Накопленная жидкость, тыс т':'Жидкость, тыс т',
                'Накопленный ПНГ':'ПНГ, млн м3'}[profil] #перевод из накоп в обычную
    #препроц для факта
    chart_df=read_file(fact_filename,'lite') 

    if deviat_chek:
        mean_values = chart_df[data_columns].mean() # Вычислить среднее значение для каждого столбца
        lower_bound = mean_values * (1-percent/100)
        upper_bound = mean_values * (1+percent/100)
        chart_df = chart_df[chart_df[data_columns].apply(lambda x: x.between(lower_bound[x.name], upper_bound[x.name])).all(axis=1)] #Отфильтровать DF методом .between

    chart_df = chart_df[
        (chart_df['Месторождение'].isin(field)) &
        (chart_df['Пласт'].isin(horizon)) &
        (chart_df['Годы'].isin(range(1, 11))) &
        (chart_df['Длина горизонтального ствола'].between(lgs[0], lgs[1])) &
        (chart_df['Число стадий'].between(nfrac[0], nfrac[1])) &
        (chart_df['Масса проппанта на стадию'].between(mprop[0], mprop[1]))
    ]

    chart_df[f'{profil} дисконтирование']=chart_df[profil]*((1+coef_discont/100)**chart_df['Годы'])**(-1)
    #препроц для ИИ
    ai_forecast = read_file(ai_filename,'lite')
    ai_forecast=ai_forecast[(ai_forecast['Месторождение'].isin(field_ai)) & (ai_forecast['Пласт'].isin(horizon_ai))]
    ai_forecast[f'{profil} дисконтирование']=ai_forecast[profil]*((1+coef_discont/100)**ai_forecast['Годы'])**(-1)

    if profil not in ['ГФ, м3/т','Обв, %']: #профиля в списке не нормируем 
    #_____________________________________________________
        ctx = callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        if trigger_id:
            button_states = [click_perm,click_nfrac,click_hoil,click_heff,click_mprop,click_mu]
            selected_buttons = [i for i, state in enumerate(button_states, start=1) if state % 2 != 0]
            if selected_buttons: #если не пустые
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                'Средняя эффективная мощность коллектора (ГИС)','Масса проппанта на стадию','1/Вязкость'] 
                divisor = chart_df[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                chart_df[profil]=chart_df[profil] / divisor
                chart_df[f'{profil} дисконтирование']=chart_df[profil] / divisor #for discont
                ai_forecast[profil]=ai_forecast[profil] / divisor
                ai_forecast[f'{profil} дисконтирование']=ai_forecast[profil] / divisor #for discont
    #цикл для расчета таблиц по критериям
    tables=[]
    Perc_func = {'P10': partial(np.percentile, q=90),
                 'Среднее': partial(np.mean),
                 'P50': partial(np.percentile, q=50),
                 'P90': partial(np.percentile, q=10)} #маппинг для удобства

    num_table=sorted(num_table, key=lambda x: int(x[1:])) #сортировка от 10 до 90
    for i in num_table: #['P50','P10']
        p,p_disc=get_percentile(chart_df,profil,Perc_func[i]), get_percentile(chart_df,f'{profil} дисконтирование',Perc_func[i])
        p_ai,p_ai_disc=get_percentile(ai_forecast,profil,Perc_func[i]), get_percentile(ai_forecast,f'{profil} дисконтирование',Perc_func[i])
        Ei=np.abs((p-p_ai))/p*100 #за три года
        criteria_val=np.round(np.array([np.mean(Ei[:3]),                                            #1
                              np.max(Ei[:3]),                                                       #2
                              np.abs((np.sum(p_ai)-np.sum(p))/np.sum(p))*100,                       #3
                              np.abs((np.sum(p_ai_disc)-np.sum(p_disc))/np.sum(p_disc))*100]),1)    #4
        
        status=["🟢" if value <= 10 else "🟡" if 10 < value <= 12.5 else "🔴" for value in criteria_val]
        tables.append(html.H6(f'Таблица {i}'))  # Добавляем заголовок
        table = dash_table.DataTable(
            id=f'table-criteria-{i}',
            columns=[{"name": col, "id": col} for col in ['Критерий','Значение, %','Статус']],
            data=pd.DataFrame({'Критерий':['Критерий 1', 'Критерий 2', 'Критерий 3','Критерий 4'],'Значение, %':criteria_val,'Статус':status}).to_dict('records'),
            style_table={'margin-bottom': '15px'},
            style_cell={'minWidth': '50px', 'width': '50px', 'maxWidth': '50px',
                        'overflow': 'hidden','textOverflow': 'ellipsis',
                        'textAlign':'left', #'padding': '10px',
                        'backgroundColor': '#e6f7ff'},
            style_header={'backgroundColor': '#00a2e8','fontWeight': 'bold','color': 'white'})
        tables.append(html.Div(table, style={'margin-bottom': '10px'}))
    #=============Таблица подбора профиля===================================================================================================================

    #Определяем функцию, которая вычисляет метрику для заданного значения i
    def metric(percentile,target):
        predictions = get_percentile(chart_df,'Нефть, тыс т',partial(np.percentile,q=percentile))
        return np.sqrt(np.mean((predictions[:3]-target[:3])**2))

    tables_percentil=[html.H6(f'Таблица подбора профилей')]
    df_0=pd.DataFrame(columns=['Профиль','Подобранный профиль'])
    for i in profil_percentile: #['P50','P10','Среднее']
        target = get_percentile(ai_forecast,'Нефть, тыс т',Perc_func[i]) #находим профиль для которого далее считаем персентиль
        result = 100-round(minimize_scalar(fun=lambda x: metric(x, target), bounds=(1, 99), method='bounded').x,0) #вычисление персентиля для выбранных профилей
        df_0=pd.concat([df_0, pd.DataFrame({'Профиль':[i],'Подобранный профиль':f'P{int(result)}'}) #общий дф со всеми профилями
                        ]) 

    table = dash_table.DataTable(
        id=f'table-percentile-{i}',
        columns=[{"name": col, "id": col} for col in ['Профиль','Подобранный профиль']],
        data=df_0.to_dict('records'),
        style_table={'margin-bottom': '15px'},
        style_cell={'minWidth': '50px', 'width': '50px', 'maxWidth': '50px',
                    'overflow': 'hidden','textOverflow': 'ellipsis',
                    'textAlign':'left', #'padding': '10px',
                    'backgroundColor': '#e6f7ff'},
        style_header={'backgroundColor': '#00a2e8','fontWeight': 'bold','color': 'white'})
        
    tables_percentil.append(html.Div(table, style={'margin-bottom': '10px','width':'500px'}))
    #======================================================================================================================================================
    #создание merge df факт и прогноз
    profil_mvr_profil={'Нефть, тыс т':'Нефть, тыс т', 'Накопленная нефть, тыс т':'Нефть, тыс т', 'Жидкость, тыс т':'Жидкость, тыс т', 'Накопленная жидкость, тыс т':'Жидкость, тыс т',
                       'ПНГ, млн м3':'Нефть, тыс т', 'Накопленный ПНГ, млн м3':'Нефть, тыс т', 'ГФ, м3/т':'Нефть, тыс т', 'Обв, %':'Нефть, тыс т'}
    '''
    df_merg=pd.merge(chart_df,ai_forecast,on=['Кластер','Месторождение','Пласт','Скважина','Годы',*list(columns_newcolumns.keys())[:-6]])[['Кластер',
                                                                                        'Месторождение','Пласт','Скважина','Годы',*list(columns_newcolumns.keys())[:-6],
                                                                                        'Нефть, тыс т_x','Нефть, тыс т_y','Жидкость, тыс т_x','Жидкость, тыс т_y']]. \
                rename(columns={'Нефть, тыс т_x':'Нефть, тыс т', 'Нефть, тыс т_y':'Нефть ИИ, тыс т','Жидкость, тыс т_x':'Жидкость, тыс т', 'Жидкость, тыс т_y':'Жидкость ИИ, тыс т'})
    #формироание пользовательской выборки
    df_merg=df_merg[(df_merg['Месторождение'].isin(field)) & (df_merg['Пласт'].isin(horizon))]
    df_merg=df_merg[(df_merg['Длина горизонтального ствола']>= lgs[0]) & (chart_df['Длина горизонтального ствола']<= lgs[1])]
    df_merg=df_merg[(df_merg['Число стадий']>= nfrac[0]) & (df_merg['Число стадий']<= nfrac[1])]
    df_merg=df_merg[(df_merg['Масса проппанта на стадию']>= mprop[0]) & (chart_df['Масса проппанта на стадию']<= mprop[1])]

    #df_merg[f'{profil} дисконтирование']=chart_df[profil]*((1+coef_discont/100)**chart_df['Годы'])**(-1)

    df_merg['Относительная ошибка годовой добычи, %']=np.abs((df_merg['Нефть, тыс т']-df_merg[' ИИ,'.join(profil.split(','))]))/df_merg['Нефть, тыс т']*100
    #--
    df_merg['Накопленная нефть, тыс т']=df_merg.groupby(['Скважина'])['Нефть, тыс т'].cumsum()
    df_merg['Накопленная нефть ИИ, тыс т']=df_merg.groupby(['Скважина'])[' ИИ,'.join(profil.split(','))].cumsum()
    #--
    df_merg['Нефть дисконт, тыс т']=df_merg['Нефть, тыс т']*((1+coef_discont/100)**df_merg['Годы'])**(-1)
    df_merg['Нефть дисконт ИИ, тыс т']=df_merg[' ИИ,'.join(profil.split(','))]*((1+14/100)**df_merg['Годы'])**(-1)
    #--
    df_merg['Накопленная дисконт нефть, тыс т']=df_merg.groupby(['Скважина'])['Нефть дисконт, тыс т'].cumsum()
    df_merg['Накопленная дисконт нефть ИИ, тыс т']=df_merg.groupby(['Скважина'])['Нефть дисконт ИИ, тыс т'].cumsum()
    #--
    df_merg['Относительная ошибка накоп. дисконт добычи, %']=np.abs(df_merg['Накопленная дисконт нефть, тыс т']-df_merg['Накопленная дисконт нефть ИИ, тыс т'])/df_merg['Накопленная дисконт нефть, тыс т']*100
    df_merg['Абс ош. добычи нефти, тыс т']=np.abs(df_merg[profil]-df_merg[' ИИ,'.join(profil.split(','))])
    #
    bins=range(0, int(df_merg['Накопленная нефть, тыс т'].max()) + 5, 20) #для накоп добычи
    df_merg['Диапазон по накоп. добыче']=pd.cut(df_merg.loc[df_merg['Годы']==10]['Накопленная нефть, тыс т'], right=False, 
                                                bins=bins,
                                                labels=[f"от {bins[i]} до {bins[i+1]} тыс.т" for i in range(len(bins)-1)])
    
    df_merg['Диапазон по накоп. добыче']=df_merg['Диапазон по накоп. добыче'].cat.add_categories(['Более 160 тыс.т'])
    #
    df_merg.loc[df_merg['Накопленная нефть, тыс т'] > 160, 'Диапазон по накоп. добыче'] = "Более 160 тыс.т"

    #построение графика "Относительная ошибка накоп. дисконт добычи, %"
    fig = px.histogram(df_merg[df_merg['Годы']==10],x='Относительная ошибка годовой добычи, %',opacity=0.6, nbins=100,range_x=[-5,105],
                       title=f'Кластер {3}. Распределение относительной ошибки накоп. дисконт добычи',
                       color='Диапазон по накоп. добыче') #цвет надо будет добавить на откуп пользователю

    fig.add_trace(go.Scatter(x=[np.percentile(df_merg[df_merg['Годы']==10]['Относительная ошибка годовой добычи, %'], 90)], y=[0],
                                        name='MAPE P10',mode='markers',marker=dict(size=15,color='green',symbol='0'),
                                        hovertemplate=f"Р10 :<br>"+"%{x:.1f} %<extra></extra>"))

    fig.add_trace(go.Scatter(x=[np.percentile(df_merg[df_merg['Годы']==10]['Относительная ошибка годовой добычи, %'], 50)], y=[0], 
                                        name='MAPE P50',mode='markers',marker=dict(size=15,color='yellow',symbol='0'),
                                        hovertemplate=f", :<br>"+"%{x:.1f} %<extra></extra>"))

    fig.add_trace(go.Scatter(x=[np.percentile(df_merg[df_merg['Годы']==10]['Относительная ошибка годовой добычи, %'], 10)], y=[0],
                                    name='MAPE P90',mode='markers',marker=dict(size=15,color='red',symbol='0'),
                                    hovertemplate=f"Р90, :<br>"+"%{x:.1f} %<extra></extra>"))    
    '''
    fig=go.Figure()
    return tables,tables_percentil, fig

#-------------------------------------------калбэк для графиков ТАБ2 (Аналитика по факту)----------------------------------------------------------------
#------------------------------------------ГИСТОГРАММА Параметров заканчивания---*-----------------------------------------------------------------------
@app.callback(
    Output('wellcomp histogram tab2', 'figure'),
    [State('upload fact data', 'filename')],

    [Input('fact_data-slide-filtering','data'), #Подгрузка набора фильтров для факт выборки-тригер
     Input('plast-selector', 'value'),
     Input('variable-selector', 'value'),
     Input('rb_hist_tab2','value'),
     Input('rb2_hist_tab2','value')]
)
def completion_geology_histogram(fact_filename,fact_viborka,horizon,param,grup,axis):
    if (fact_filename is None) and (horizon is not None):
        return px.bar()

    data=json.loads(fact_viborka)
    chart_df=make_viborka_df(read_file(fact_filename,'lite'), data, 'None') #открываем файл из кэша и сразу применяем фильтры из словаря в функции make_viborka_df()
    
    pivot_chart_df=chart_df.groupby(grup,as_index=False)[[param]].agg('mean')

    if axis=='Ось х-объекты':
        pivot_chart_df=pivot_chart_df.sort_values(by=grup)
        fig = px.bar(pivot_chart_df,y=param,x=grup,color=grup,opacity=0.6)
        fig.update_layout(yaxis1=dict(title=param)) 
    elif axis=='Ось х-значения':
        fig = px.histogram(pivot_chart_df,x=param,color=grup,opacity=0.6, nbins=50)
        fig.update_layout(xaxis1=dict(dtick={'Число стадий':1,'Длина горизонтального ствола':100,'Межпортовое расстояние':25,'Масса проппанта на стадию':10}[param]),
                          yaxis1=dict(title=' '))

    return fig

#===================================================================Формирование таблицы средней скважины по фильтрам "Кластер-Месторождние-пласт"========================================================
#колонки по которым будет осреднение, +доается более укороченное имя
columns_newcolumns={'Средняя проницаемость (ГИС)':'Кпр, мД',
                    'Средняя эффективная мощность коллектора (ГИС)':'Нэф, м','Средний коэффициент нефтенасыщенности (Кн)':'Кн, д.ед',
                    'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)':'ННТ, м',
                    'Начальное пластовое давление':'Рпл, МПа',
                    'Средняя вязкость флюида в пластовых условиях':'Вязкость, мПа*с',
                    'Газовый фактор':'Газовый фактор',
                    'Расстояние между рядами скважин':'Расстояние между рядами скважин',
                    'Длина горизонтального ствола':'Длина гор. ствола',
                    'Масса проппанта на стадию':'Масса проппанта на стадию',
                    'Число стадий':'Число стадий',
                    #гмм, для full верисии табл
                    'Градиент начального давления закрытия, атм/м':'gradP давления закрытия, атм/м',
                    'Градиент горизонтального напряжения, атм/м':'gradP горизонтального напряжения, атм/м',
                    'Средний динамический коэффициент Пуассона для песчаника':'Коэф. Пуассона для песчаника',
                    'Средний динамический коэффициент Пуассона для алевролита/аргиллита':'Коэф. Пуассона для алевролита/аргиллита',
                    'Средний динамический модуль Юнга для песчаника':'Модуль Юнга для песчаника',
                    'Средний динамический модуль Юнга для алевролита/аргиллита':'Модуль Юнга для алевролита/аргиллита'}

@app.callback(
    [Output('mean-well-table', 'columns'),
     Output('mean-well-table', 'data'), #для отображения таблицы
     Output('mean-well-table-store','data')], #для хранения в store, для экспорта

    [State('upload fact data', 'filename')],
    [Input('cluster-selector', 'value'),
     Input('field-selector', 'value'),
     Input('plast-selector','value'),
     Input('lgs-slider','value'),
     Input('nfrac-slider','value'),
     Input('row-selector', 'value')])

def mean_well_table(fact_filename, cluster,field,horizon,lgs,nfrac,row_selector):
    if (fact_filename is None) or (horizon is None):
        return [{"name": i, "id": i} for i in ['Параметры','Средняя скважина']],[], None #pd.DataFrame().to_json(date_format='iso', orient='split')
        #сверху проерка на отсутствие данных, далее все как и раньше
    chart_df=read_file(fact_filename,'full')
    
    chart_df=chart_df[(chart_df['Месторождение'].isin(field)) & (chart_df['Пласт'].isin(horizon))]
    chart_df=chart_df.loc[chart_df[chart_df['Годы'].isin(range(1,11))].index] #целые значения по годам в дф

    chart_df=chart_df[(chart_df['Длина горизонтального ствола']>= lgs[0]) & (chart_df['Длина горизонтального ствола']<= lgs[1])]
    chart_df=chart_df[(chart_df['Число стадий']>= nfrac[0]) & (chart_df['Число стадий']<= nfrac[1])]

    chart_df=chart_df.rename(columns=columns_newcolumns)
    
    cluster=list(map(str,cluster))
    df_head=pd.DataFrame(index=['Кластер','Месторождение','Пласт'],columns=['Средняя скважина'],data=[', '.join(cluster),', '.join(field),', '.join(horizon)])

    chart_df=chart_df.drop_duplicates(subset=['Скважина']).reset_index(drop=True) #удаление дубликатов для правильной статистики
    chart_df=pd.DataFrame(chart_df[columns_newcolumns.values()].mean(),columns=['Средняя скважина'])

    df_mean_well=pd.concat([df_head,chart_df])
    df_mean_well['Параметры']=df_mean_well.index

    if row_selector=='short':
        return [{"name": i, "id": i} for i in ['Параметры','Средняя скважина']], df_mean_well.iloc[:-6].to_dict('records'), df_mean_well.to_dict('records')
    else:
        return [{"name": i, "id": i} for i in ['Параметры','Средняя скважина']], df_mean_well.to_dict('records'), df_mean_well.to_dict('records')


#калбэк для экспорта таблицы средней скважины в файл
@app.callback(
    Output('mean-well-table-download', 'data'), #обращение к id upload
    [Input('mean-well-table-export', 'n_clicks')], #обращение к id button export
    [State('mean-well-table-store', 'data')] #обращение к id самой таблицы
)

def export_wellmean_to_excel(n_click, data):
    if n_click > 0 and data is not None:
        df=pd.DataFrame(data,columns=['Параметры','Средняя скважина']).T
        df.columns=df.loc['Параметры']
        df=df.iloc[1:]
        df=df.rename(columns={v: k for k, v in columns_newcolumns.items()}) #меням местами клю-значение
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        buffer.seek(0)
        return dcc.send_bytes(buffer.getvalue(), "data.xlsx")
    else:
        return None
    
'''
app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks > 0) {
            setTimeout(function() {
                window.dash_clientside.callbacks.download_complete.update({data: true});
            }, 1000); // Adjust the timeout as needed
        }
        return null;
    }
    """,
    Output('profil-table-download-store', 'data'),
    Input('profil-export-button', 'n_clicks'))

@app.callback(
    Output('modal-profil', 'is_open'),
    [Input('profil-table-download-store', 'data')],
    [State('modal-profil', 'is_open')])

def toggle_modal(download_complete, is_open):
    if download_complete:
        return True
    return is_open
'''

#-------------------------------------------калбэк для графиков ТАБ3 (Аналитика МВР расчётов)----------------------------------------------------------------
#------------------------------------------ГИСТОГРАММА @Показатель от параметра---*-----------------------------------------------------------------------
rules_lgs={'Qн 1 мес, т/сут':True,     'Qж 1 мес, т/сут':True, 
           'Qн 13 мес, т/сут':True,    'Qж 13 мес, т/сут':True,
           'НДН за 1 год, тыс.т':True, 'НДЖ за 1 год, тыс.т':True,
           'НДН за 10 лет, тыс.т':True,'НДЖ за 10 лет, тыс.т':True}

rules_mprop={'Qн 1 мес, т/сут':True,     'Qж 1 мес, т/сут':True, 
             'Qн 13 мес, т/сут':True,    'Qж 13 мес, т/сут':True,
             'НДН за 1 год, тыс.т':None, 'НДЖ за 1 год, тыс.т':True,
             'НДН за 10 лет, тыс.т':None,'НДЖ за 10 лет, тыс.т':True}

rules_nfrac={'Qн 1 мес, т/сут':True,     'Qж 1 мес, т/сут':True, 
             'Qн 13 мес, т/сут':None,    'Qж 13 мес, т/сут':None,
             'НДН за 1 год, тыс.т':True, 'НДЖ за 1 год, тыс.т':True,
             'НДН за 10 лет, тыс.т':None,'НДЖ за 10 лет, тыс.т':None}

@app.callback(
    [Output("nd1-lgs", "figure"),
     Output("q1-lgs", "figure"),
     Output("nd10-lgs", "figure"),
     Output("q13-lgs", "figure"),

     Output("nd1-mprop", "figure"),
     Output("q1-mprop", "figure"),
     Output("nd10-mprop", "figure"),
     Output("q13-mprop", "figure"),

     Output("nd1-nfrac", "figure"),
     Output("q1-nfrac", "figure"),
     Output("nd10-nfrac", "figure"),
     Output("q13-nfrac", "figure")],
    [State('upload mvr data', 'filename')],
    [Input("mvr-table","virtualRowData"),
     Input("profil-selector","value")])

def mvr_analisis(mvr_filename,filter_table,profil):
    '''
    obj=pd.read_excel('газраз\Газовый_Разведчик_МВР1_ИД_для_ФЭМ.xlsx',skiprows=2) #читаем файл (строка-расчёт)
    params0=['Длина горизонтального ствола 1 в метрах','Тип ГРП Ствол 1','Расход ГРП 1','Количество стадий 1','Масса пропанта на стадию Ствол 1',
             'Добыча нефти, тыс.т.',                              #доб 1 мес
             'Добыча нефти, тыс.т..12',                           #доб за 1 год
             'Добыча нефти, тыс.т..13',                           #доб 13 мес
             *[f'Добыча нефти, тыс.т..{25+i}' for i in range(9)]] #доб 2-10 годы
    obj_params=obj[[*params0]]   #берём только нужные колонки
    #--------расчет для метрик-показатели разработки---------------      
    obj_params['НДН за 10 лет, тыс.т']=obj_params[['Добыча нефти, тыс.т..12',*[f'Добыча нефти, тыс.т..{25+i}' for i in range(9)]]].sum(axis=1)
    obj_params['Qн 1 мес, т/сут']=obj_params['Добыча нефти, тыс.т.']/30*1000
    obj_params['Qн 13 мес, т/сут']=obj_params['Добыча нефти, тыс.т..13']/30*1000
    obj_params['Концентрация']='Ст'
    obj_params=obj_params.rename(columns={'Длина горизонтального ствола 1 в метрах':'Длина горизонтального ствола',
                                          'Тип ГРП Ствол 1':'Тип ГРП',
                                          'Расход ГРП 1':'Расход ГРП',
                                          'Количество стадий 1':'Количество стадий',
                                          'Масса пропанта на стадию Ствол 1':'Масса пропанта на стадию',
                                          'Добыча нефти, тыс.т..12':'НДН за 1 год, тыс.т'})
    '''
    if (mvr_filename is None):
        return [go.Figure()]*12
    
    obj_params=pd.DataFrame(filter_table)
    #obj_params=read_file(mvr_filename,'mvr') #читаем файл из кэша
    
    #расчёт гистограммы @Показатель от Lгс
    obj_gr=obj_params.groupby(['Тип ГРП','Длина горизонтального ствола'],
                as_index=False)[['Qн 1 мес, т/сут', 
                                 'Qн 13 мес, т/сут',
                                 'НДН за 1 год, тыс.т',
                                 'НДН за 10 лет, тыс.т']].agg('mean').copy()
    
    obj_gr['Цвет'] = obj_gr['Тип ГРП'].map({'HIWAY':'#4472C4','XL+ПАА':'#5B9BD5','ПАА':'#A5A5A5','ВГРП':'#ED7D31','Стандарт':'#FFC000'})

    num_cols=obj_gr['Тип ГРП'].nunique()
    fig_array=[]
    for graph in ['НДН за 1 год, тыс.т','Qн 1 мес, т/сут','НДН за 10 лет, тыс.т','Qн 13 мес, т/сут']:

        fig=make_subplots(rows=1, cols=int(num_cols), shared_yaxes=True,horizontal_spacing=0.005)
        for i, cat in enumerate(obj_gr['Тип ГРП'].unique()):
            x=obj_gr[obj_gr['Тип ГРП']==cat]['Длина горизонтального ствола']
            y=obj_gr[obj_gr['Тип ГРП']==cat][graph]
            #----------------------------------------------ПРИМЕНЯЕМ ЗАКРАСКУ ТЕКСТА ОТ ПРАВИЛА---------------------------------
            if rules_lgs[graph]!=None: #берем только правила, где есть зависимость
                diffs=np.diff(y)
                is_monotonic = np.all(diffs >= 0) or np.all(diffs <= 0) #проверка на монотонность (True/False)
                color_name={True:'grey',False:'red'}[is_monotonic] #монотонность-базовый цвет. иначе красный
            else:
                color_name='grey'
            #--------------------------------------------------------------------------------------------------------------------
            fig.add_trace(go.Bar(
                        x=x,
                        y=y,
                        name=cat,
                        marker_color=obj_gr[obj_gr['Тип ГРП']==cat]['Цвет'],
                        ), row=1, col=i+1)
            fig.update_xaxes(title_text=cat,
                             title_font=dict(size=14, color=color_name), 
                             tickmode='array',
                             tickvals=x.astype(str),
                             ticktext=x.astype(str),
                             tickangle=65, #угол тиков
                             row=1, col=i+1)
            fig.update_layout(yaxis=dict(title=graph))
        fig_array.append(fig)
#===========================================расчёт гистограммы @Показатель от Массы проппаннта=========================================================================
    obj_gr=obj_params.groupby(['Тип ГРП','Расход ГРП','Концентрация','Масса пропанта на стадию'],
                as_index=False)[['Qн 1 мес, т/сут', 
                                 'Qн 13 мес, т/сут',
                                 'НДН за 1 год, тыс.т',
                                 'НДН за 10 лет, тыс.т']].agg('mean').copy()
    
    obj_gr['Цвет'] = obj_gr['Тип ГРП'].map({'HIWAY':'#4472C4','XL+ПАА':'#5B9BD5','ПАА':'#A5A5A5','ВГРП':'#ED7D31','Стандарт':'#FFC000'})

    num_cols=obj_gr.groupby(['Тип ГРП','Расход ГРП'],as_index=True)[['Концентрация']].agg('nunique').sum(axis=0).values[0]
    for graph in ['НДН за 1 год, тыс.т','Qн 1 мес, т/сут','НДН за 10 лет, тыс.т','Qн 13 мес, т/сут']: #цикл для 4ёх графиков показателей
        
        counter = 0
        fig=make_subplots(rows=1, cols=int(num_cols), shared_yaxes=True,horizontal_spacing=0.005)
        for i, cat in enumerate(obj_gr['Тип ГРП'].unique()): # перебор типов ГРП 1 уровень
            df_filter=obj_gr[obj_gr['Тип ГРП']==cat]    # фильтрация по типу
            for j, sub1_cat in enumerate(df_filter['Расход ГРП'].unique()):      # перебор расходов ГРП 2 уровень
                df_filter2=df_filter[df_filter['Расход ГРП']==sub1_cat]          # фильтрация по расходу
                for k, sub2_cat in enumerate(df_filter['Концентрация'].unique()): 
                    df_filter3=df_filter2[df_filter2['Концентрация']==sub2_cat].sort_values(by='Масса пропанта на стадию')
                    counter+=1          
                    x=df_filter3['Масса пропанта на стадию']
                    y=df_filter3[graph]
                    #----------------------------------------------ПРИМЕНЯЕМ ЗАКРАСКУ ТЕКСТА ОТ ПРАВИЛА---------------------------------
                    if rules_mprop[graph]!=None: #берем только правила, где есть зависимость
                        diffs=np.diff(y)
                        is_monotonic = np.all(diffs >= 0) or np.all(diffs <= 0) #проверка на монотонность (True/False)
                        color_name={True:'grey',False:'red'}[is_monotonic] #монотонность-базовый цвет. иначе красный
                    else:
                        color_name='grey'
                    #--------------------------------------------------------------------------------------------------------------------
                    fig.add_trace(go.Bar(
                        x=x,
                        y=y,
                        name=f"{cat}, Расход {sub1_cat}",
                        marker_color=df_filter3[df_filter3['Тип ГРП']==cat]['Цвет'],
                    ), row=1, col=counter)
                    fig.update_xaxes(
                                 title_text=f"{cat},<br>Расход {sub1_cat}, <br>Конц. {sub2_cat}",
                                 title_font=dict(size=9, color=color_name),
                                 tickmode='array',
                                 tickvals=x.astype(str),
                                 ticktext=x.astype(str),
                                 row=1, col=counter)
            fig.update_layout(yaxis=dict(title=graph))
        fig_array.append(fig)
#расчёт гистограммы @Показатель от числа стадий

    obj_gr=obj_params.groupby(['Тип ГРП','Расход ГРП','Концентрация','Количество стадий'],
                as_index=False)[['Qн 1 мес, т/сут', 
                                 'Qн 13 мес, т/сут',
                                 'НДН за 1 год, тыс.т',
                                 'НДН за 10 лет, тыс.т']].agg('mean').copy()
    
    obj_gr['Цвет'] = obj_gr['Тип ГРП'].map({'HIWAY':'#4472C4','XL+ПАА':'#5B9BD5','ПАА':'#A5A5A5','ВГРП':'#ED7D31','Стандарт':'#FFC000'})
    num_cols=obj_gr.groupby(['Тип ГРП','Расход ГРП'],as_index=True)[['Концентрация']].agg('nunique').sum(axis=0).values[0]
    for graph in ['НДН за 1 год, тыс.т','Qн 1 мес, т/сут','НДН за 10 лет, тыс.т','Qн 13 мес, т/сут']: #цикл для 4ёх графиков показателей
        
        counter = 0
        fig=make_subplots(rows=1, cols=int(num_cols), shared_yaxes=True,horizontal_spacing=0.005)
        for i, cat in enumerate(obj_gr['Тип ГРП'].unique()): # перебор типов ГРП 1 уровень
            df_filter=obj_gr[obj_gr['Тип ГРП']==cat]    # фильтрация по типу
            for j, sub1_cat in enumerate(df_filter['Расход ГРП'].unique()):      # перебор расходов ГРП 2 уровень
                df_filter2=df_filter[df_filter['Расход ГРП']==sub1_cat]          # фильтрация по расходу
                for k, sub2_cat in enumerate(df_filter['Концентрация'].unique()): 
                    df_filter3=df_filter2[df_filter2['Концентрация']==sub2_cat].sort_values(by='Количество стадий')
                    counter+=1          
                    x=df_filter3['Количество стадий']
                    y=df_filter3[graph]
                    #----------------------------------------------ПРИМЕНЯЕМ ЗАКРАСКУ ТЕКСТА ОТ ПРАВИЛА---------------------------------
                    if rules_nfrac[graph]!=None: #берем только правила, где есть зависимость
                        diffs=np.diff(y)
                        is_monotonic = np.all(diffs >= 0) or np.all(diffs <= 0) #проверка на монотонность (True/False)
                        color_name={True:'grey',False:'red'}[is_monotonic] #монотонность-базовый цвет. иначе красный
                    else:
                        color_name='grey'
                    #--------------------------------------------------------------------------------------------------------------------
                    fig.add_trace(go.Bar(
                        x=x,
                        y=y,
                        name=f"{cat}, Расход {sub1_cat}",
                        marker_color=df_filter3[df_filter3['Тип ГРП']==cat]['Цвет'],
                    ), row=1, col=counter)
                    fig.update_xaxes(
                                 title_text=f"{cat},<br>Расход {sub1_cat}, <br>Конц. {sub2_cat}",
                                 title_font=dict(size=9, color=color_name),
                                 tickmode='array',
                                 tickvals=x.astype(str),
                                 ticktext=x.astype(str),
                                 row=1, col=counter)
            fig.update_layout(yaxis=dict(title=graph))
        fig_array.append(fig)
    return fig_array
#--------------------------------------------------------------------------------------------------------------------------------------------------
#========================================================================callbackы для апгрейда layout=============================================

# collapse фильтры Залежь, куст
@app.callback(
    [Output("collapse-zalej_kust", "is_open"),
     Output("collapse-button-zalej_kust", "children")],
    [Input("collapse-button-zalej_kust", "n_clicks")],
    [State("collapse-zalej_kust", "is_open")])
def toggle_collapse(n_click, is_open):
    if n_click:
        if is_open:
            return False, "Показать фильтры по залежам и кустам"
        else:
            return True, "Убрать фильтры по залежам и кустам"
    return is_open, "Показать фильтры по залежам и кустам"


# collapse фильтры заканчивания
@app.callback(
    [Output("collapse-well_filter", "is_open"),
     Output("collapse-button-well_filter", "children")],
    [Input("collapse-button-well_filter", "n_clicks")],
    [State("collapse-well_filter", "is_open")])
def toggle_collapse(n_click, is_open):
    if n_click:
        if is_open:
            return False, "Показать фильтры по заканчиванию"
        else:
            return True, "Убрать фильтры по заканчиванию"
    return is_open, "Показать фильтры по заканчиванию"

#collapse фильтры ГФХ 
@app.callback(
    [Output("collapse-gfh", "is_open"),
     Output("collapse-button-gfh", "children")],
    [Input("collapse-button-gfh", "n_clicks")],
    [State("collapse-gfh", "is_open")])
def toggle_collapse(n_click, is_open):
    if n_click:
        if is_open:
            return False, "Показать фильтры по ГФХ"
        else:
            return True, "Убрать фильтры по ГФХ"
    return is_open, "Показать фильтры по ГФХ"

#collapse фильтры PVT 
@app.callback(
    [Output("collapse-pvt", "is_open"),
     Output("collapse-button-pvt", "children")],
    [Input("collapse-button-pvt", "n_clicks")],
    [State("collapse-pvt", "is_open")])
def toggle_collapse(n_click, is_open):
    if n_click:
        if is_open:
            return False, "Показать фильтры по PVT"
        else:
            return True, "Убрать фильтры по PVT"
    return is_open, "Показать фильтры по PVT"

#сравнение профилей
@app.callback( 
    [Output("collapse-2", "is_open"),
     Output("collapse-button-2", "children")],
    [Input("collapse-button-2", "n_clicks")],
    [State("collapse-2", "is_open")])
def toggle_collapse(n_click, is_open):
    if n_click:
        if is_open:
            return False, "Показать таблицы сравнения профилей"
        else:
            return True, "Убрать таблицы сравнения профилей"
    return is_open, "Показать таблицы сравнения профилей"

#подбор профилей
@app.callback( 
    [Output("collapse-3", "is_open"),
     Output("collapse-button-3", "children")],
    [Input("collapse-button-3", "n_clicks")],
    [State("collapse-3", "is_open")])
def toggle_collapse(n_click, is_open):
    if n_click:
        if is_open:
            return False, "Показать функционал подбора профилей"
        else:
            return True, "Убрать функционал подбора профилей"
    return is_open, "Показать функционал подбора профилей"

#фильтр таблицы МВР
@app.callback( 
    [Output("collapse-4", "is_open"),
     Output("collapse-button-4", "children")],
    [Input("collapse-button-4", "n_clicks")],
    [State("collapse-4", "is_open")])
def toggle_collapse(n_click, is_open):
    if n_click:
        if is_open:
            return False, "Показать таблицу фильтрации МВР"
        else:
            return True, "Убрать таблицу фильтрации МВР"
    return is_open, "Показать таблицу фильтрации МВР"

if __name__ == '__main__': # Run the app
    app.run(debug=True) #True=dev mode False

    
