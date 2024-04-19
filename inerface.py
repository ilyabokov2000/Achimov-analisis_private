from dash import Dash, html, dash_table,dcc,html,ctx,callback_context
from dash.dependencies import Output, Input, State
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time
#-------------------------------------------------------------------------------------------------------------------------------------
df=pd.read_excel('Профиля Приобское v2.xlsx',sheet_name='Приобское') #считывание изначального файла
df['Нефть уд., тыс т']=df['Нефть, тыс т'] #/df['Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)']/df['Число стадий']
df['Жидкость уд., тыс т']=df['Жидкость, тыс т']
df['ПНГ уд., млн м3']=df['ПНГ, млн м3']
df['ГФ, м3/т']=df['ПНГ, млн м3'] / df['Нефть, тыс т']*1000 #Фактический ГФ из профилей
df['Обв, %']=(df['Жидкость, тыс т']-df['Нефть, тыс т']) / df['Жидкость, тыс т']*100 #Фактическая обв, %
df['Межпортовое расстояние']=df['Длина горизонтального ствола'] / (df['Число стадий']+1)

ind=df[df['Годы'].isin(range(1,11))].index #индекс целого года

cluster_field_dict={k: g["Месторождение"].tolist() for k,g in df[['Кластер','Месторождение']].drop_duplicates().groupby("Кластер")}
field_plast_dict={k: g["Пласт"].tolist() for k,g in df[['Месторождение','Пласт']].drop_duplicates().groupby("Месторождение")}
#----------------------------------------------------------------VIDGETS---------------------------------------------------------------------
#Выпадающие списки--------------------------------------------------
cluster_selector = dcc.Dropdown(
    id='cluster-selector',
    options=list(df['Кластер'].unique()),
    value=list(df['Кластер'].unique())[:1],
    multi=True)

field_selector = dcc.Dropdown(
    id='field-selector',
    multi=True)

plast_selector = dcc.Dropdown(
    id='plast-selector',
    multi=True)

profil_selector=dcc.Dropdown(
    id='profil-selector',
    options=[
        {'label': html.Span(['Нефть, тыс. т'], style={'color': 'Brown', 'font-size': 20}), 'value': 'Нефть, тыс т'},
        {'label': html.Span(['Жидкость, тыс. т'], style={'color': 'Green', 'font-size': 20}), 'value': 'Жидкость, тыс т'},
        {'label': html.Span(['ПНГ, млн. м3'], style={'color': 'Gold', 'font-size': 20}), 'value': 'ПНГ, млн м3'},
        {'label': html.Span(['ГФ, м3/т'], style={'color': 'Grey', 'font-size': 20}), 'value': 'ГФ, м3/т'},
        {'label': html.Span(['Обводненность, %'], style={'color': 'blue', 'font-size': 20}), 'value': 'Обв, %'}
        ],
    value='Нефть, тыс т',
    multi=False)

label_dict={'Нефть, тыс т':['Добыча нефти','тыс. т'],
                'Жидкость, тыс т':['Добыча жидкости','тыс. т'],
                'ПНГ, млн м3':['Добыча ПНГ','млн м3'],
                'ГФ, м3/т':['Газовый фактор','м3/т'],
                'Обв, %':['Обводненность','%']}
variable_selector=dcc.Dropdown(
    id='variable-selector',
    options=['Длина горизонтального ствола','Число стадий','Межпортовое расстояние','Масса проппанта на стадию'],
    value='Число стадий',
    multi=False
)
#------------------------------------------------------------------

#------------------------------------------------------------------
#------------------------------------------------------------------------------------------------
#ТАБЫ--------------(Здесь задается контент по табам)---------------------------------------------
tab1_content=[dbc.Row([
        html.H4('Выбранный профиль – гистограмма по годам'),
        html.Hr(),
        dbc.Col([dcc.Graph(id='qstart histogram'),
                 html.Div(dcc.Slider(1,10,1,id='year-slider',value=1))],style={'width':'100px'}),
        dbc.Col([dcc.Graph(id='udeln qstart histogram')],style={'width':'100px'}),
        dbc.Row() #слайдер годы
    ]),
    dbc.Row([
        html.H4('Сравнение динамики профилей'),
        html.Hr(),
        html.Div(dcc.RadioItems(['Профиля','Ящик с усами','Точки'],'Точки',id='profil-rb')),
        html.Hr(),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='profils')])],style={'width':'100px'}),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='udeln profils')])],style={'width':'100px'})
    ]),
    dbc.Row([
        html.H4('Сравнение динамики дисконтированных профилей'),
        html.Hr(),
        html.Div(dcc.Input(id="coef discont", type="number", value=10,placeholder="Ввод ставки дисконтирования,%",style={'width':'300px','margin-bottom':'20px'})),
        html.Hr(),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='discont profils')])],style={'width':'100px'}),
        dbc.Col([dcc.Loading(type="default",children=[dcc.Graph(id='udeln discont profils')])],style={'width':'100px'})
    ])]

tab2_content=[
    dbc.Row([
        html.Div('Выбор параметра:'),
        html.Div(variable_selector, style={'width':'400px','margin-bottom':'40px'})]),
    dbc.Row([
        html.H4('Выбранный параметр – гистограмма по заканчивания'),
        html.Hr(),
        html.Div('Группировать по:'),
        dcc.RadioItems(['По кластерам','По месторождениям','По пластам','По скважинам'],'По пластам',id='rb_hist_tab2'),
        html.Hr(),
        dbc.Col(dcc.Loading(type="default",children=[dcc.Graph(id='wellcomp histogram tab2')]))   
            ])]


#------------------------------------------------------------------------------------------------
#--------------------------------------------------------------layout-----------------------------------------------------------------------
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP],suppress_callback_exceptions=True) #Initialize the app+тема BOOTSTRAP
# suppress_callback_exceptions=True для 
server = app.server

app.layout = html.Div([
    dbc.Row([
        html.H4('Приложение для аналитики АТ'),
        html.Hr(),
        html.Div('Фильтр кластера'),
        html.Div(cluster_selector, style={'width':'400px','margin-bottom':'20px'}),
        html.Hr()
    ]),
    dbc.Row([
        html.Div('Фильтр месторождения:'),
        dbc.Col(
            html.Div(field_selector, style={'width':'400px','margin-bottom':'10px'}),
            width={'size':4,'offset':0}),
        dbc.Col(
            dbc.Button('Выбрать все',id='All field',n_clicks=0,className='mr-2',style={'margin-bottom':'30px'}),align='end'), #кнопка field
        html.Hr()
    ]),
    dbc.Row([
            html.Div('Фильтр пластов:'),
            dbc.Col(
                html.Div(plast_selector, style={'width':'400px','margin-bottom':'10px'}),
                width={'size':4,'offset':0}),
            dbc.Col(
            dbc.Button('Выбрать все',id='All plast',n_clicks=0,className='mr-2',style={'margin-bottom':'30px'})), #кнопка plast
        html.Hr()
    ]),
    dbc.Row([
        dbc.Col([
            html.Div('Выбор профиля:'),
            html.Div(profil_selector, style={'width':'400px','margin-bottom':'10px'}),
            ]),
        dbc.Col([
            html.Div('Выбор нормировочных множителей:'),
            dbc.Button('Проницаемость (ГИС)',id='udeln perm',n_clicks=0,className='mr-3', style={"margin-right": "10px"}),
            dbc.Button('Число стадий',id='udeln nfrac',n_clicks=0,className='mr-3',       style={"margin-right": "10px"}),
            dbc.Button('ННТ',id='udeln hoil',n_clicks=0,className='mr-3',                 style={"margin-right": "10px"}),
            dbc.Button('Heff',id='udeln heff',n_clicks=0,                                 style={"margin-right": "10px"}),
            ],width=6
            ),
        html.Hr()                    
    ]),
    dbc.Tabs([
        dbc.Tab(tab1_content,label='Верификация профилей'),
        dbc.Tab(tab2_content,label='Аналитика факта'),
    ],id='tabs', active_tab='Верификация профилей')    # 
    ],
    style={'margin-left':'60px',
           'margin-right':'30px'})


#----------------------------калбэки для изменения в фильтрах пласта/мр, при выборе мр/кластера----------------------------------------
# Обновление второго выпадающего списка в зависимости от кластера
@app.callback(
    Output('field-selector', 'options'),
    [Input('cluster-selector', 'value')])
def update_dropdown_fields(selected_clusters):
    values=list(df['Месторождение'].loc[df['Кластер'].isin(selected_clusters)].unique()) # список месторождений из Df
    return [{'label': i, 'value': i} for i in values]


# Обновление третьего выпадающего списка в зависимости от месторождения
@app.callback(
    Output('plast-selector', 'options'),
    [Input('field-selector', 'value')])
def update_dropdown_plast(selected_fields):
    values=list(df['Пласт'].loc[df['Месторождение'].isin(selected_fields)].unique()) # список пластов из Df
    return [{'label': i, 'value': i} for i in values]
    
#-------------------------------------------калбэк для кнопок------------------------------------------------------------------------

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
     Output('udeln heff', 'style')],
    [Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac', 'n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff','n_clicks'),
     Input('profil-selector','value')]
)
def update_button_styles(click1, click2, click3, click4,profil):
    if profil not in ['ГФ, м3/т','Обв, %']:
        button_styles = [{'background-color': 'blue' if click1 % 2 != 0 else 'grey','margin-right':'10px'},
                         {'background-color': 'blue' if click2 % 2 != 0 else 'grey','margin-right':'10px'},
                         {'background-color': 'blue' if click3 % 2 != 0 else 'grey','margin-right':'10px'},
                         {'background-color': 'blue' if click4 % 2 != 0 else 'grey','margin-right':'10px'}]
    else:
        button_styles = [{'background-color': 'grey','margin-right':'10px'},
                         {'background-color': 'grey','margin-right':'10px'},
                         {'background-color': 'grey','margin-right':'10px'},
                         {'background-color': 'grey','margin-right':'10px'}]
    return button_styles

norm_mult={1:'/Средняя проницаемость (ГИС)',2:'/Число стадий',3:'/ННТ',4:'/Нэф'}
#-------------------------------------------калбэк для графиков ТАБ1------------------------------------------------------------------------
#------------------------------------------ГИСТОГРАММА СТАРТОВЫХ ДЕБИТОВ (1ЫЙ ГОД)----------------------------------------------------------
@app.callback(
    Output('qstart histogram', 'figure'),
    [Input('field-selector', 'value'),
     Input('plast-selector', 'value'),
     Input('profil-selector', 'value'),
     Input('year-slider', 'value')]
)
def qstart_histogram(field,horizon,profil,year):
    chart_df=df[(df['Месторождение'].isin(field)) & (df['Пласт'].isin(horizon))]
    chart_df=chart_df.loc[chart_df['Годы']==year] #фильтр года

    fig = px.histogram(chart_df,x=profil,color='Пласт',opacity=0.6, nbins=50)
    fig.add_trace(go.Scatter(x=np.ones(20)*chart_df[profil].mean(), y=np.linspace(0, 20, num=20),
                             name='Факт P50',mode='lines',line=dict(width=2,color='mediumseagreen'),
                             hovertemplate="Факт Р50: %{x:.3f}тыс.т/год<br>"
                            ))
    fig.update_layout(
        xaxis1=dict(title=f"{label_dict[profil][0]} в {year}-й год, {label_dict[profil][1]}"),
        yaxis1=dict(title=f'Кол-во'))
        #title=dict(text=f'Стартовая добыча 1-ый год')
    return fig
#------------------------------------------ГИСТОГРАММА УДЕЛЬНЫХ СТАРТОВЫХ ДЕБИТОВ (1ЫЙ ГОД)-----------------------------------------------------
@app.callback(
     Output('udeln qstart histogram','figure'),
    [Input('field-selector','value'),
     Input('plast-selector','value'),
     Input('profil-selector','value'),
     Input('year-slider', 'value'),
     Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac', 'n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff', 'n_clicks')])
def udeln_qstart_histogram(field,plast,profil,year,click_perm,click_nfrac,click_hoil,click_heff): 
    chart_df=df[(df['Месторождение'].isin(field)) & (df['Пласт'].isin(plast))]
    chart_df=chart_df.loc[chart_df['Годы']==year] 
    if profil not in ['ГФ, м3/т','Обв, %']: #профиля в списке не нормируем 
    #_____________________________________________________
        ctx = callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        if trigger_id:
            button_states = [click_perm,click_nfrac,click_hoil,click_heff]
            selected_buttons = [i for i, state in enumerate(button_states, start=1) if state % 2 != 0]
            if selected_buttons:
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                'Средняя эффективная мощность коллектора (ГИС)'] 
                divisor = df[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                chart_df[profil]=chart_df[profil] / divisor
    #_____________________________________________________
        p50=chart_df[profil].mean()
        fig = px.histogram(chart_df,x=profil,color='Пласт',opacity=0.6, nbins=50)
        fig.add_trace(go.Scatter(x=np.ones(20)*p50, y=np.linspace(0, 20, num=20),
            name='Удельный факт P50',mode='lines',line=dict(width=2,color='mediumseagreen'),
            hovertemplate="Факт Р50 : %{x:.3f}<br>"))

        fig.update_layout(
            xaxis1=dict(title=f'{label_dict[profil][0]} удельная в {year}-й год, {label_dict[profil][0]+"".join([norm_mult[i] for i in selected_buttons])}'),
            yaxis1=dict(title=f'Кол-во'))
            #title=dict(text=f'Удельная добыча в 1-ый год')
        return fig
    else:
        fig = px.scatter()
        return fig 
#------------------------------------------ГРАФИК ПРОФИЛЕЙ------------------------------------------------------------------------
@app.callback(
    Output('profils', 'figure'),
    [Input('field-selector', 'value'),
     Input('plast-selector', 'value'),
     Input('profil-selector', 'value'),
     Input('profil-rb', 'value')]
)
def q_profils(field,horizon,profil,graph):
    chart_df=df[(df['Месторождение'].isin(field)) & (df['Пласт'].isin(horizon))]
    ind=chart_df[chart_df['Годы'].isin(range(1,11))].index
    chart_df=chart_df.loc[ind] #целые значения по годам в дф
    #
    colors = px.colors.qualitative.Plotly[:len(chart_df['Пласт'].unique())]
    color_map = dict(zip(chart_df['Пласт'].unique(), colors))
    chart_df['Цвет пласт'] = chart_df['Пласт'].map(color_map)

    if len(horizon)!=0:
        p10=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=profil,
            aggfunc=[lambda x: np.percentile(x, 90)],margins=True,
            margins_name='P10').T['P10'].iloc[:-1].values

        p50=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=profil,
            aggfunc=[lambda x: np.percentile(x, 50)],margins=True,
            margins_name='P50').T['P50'].iloc[:-1].values
        
        p90=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=profil,
            aggfunc=[lambda x: np.percentile(x, 10)],margins=True,
            margins_name='P90').T['P90'].iloc[:-1].values
    else:
        p10,p50,p90=[],[],[]
    #time.sleep(3)
    fig=go.Figure()
    if graph=='Профиля':
        for i,f in enumerate(chart_df['Месторождение'].unique()):
            for j,h in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                j=j+i*10
                print(j)
                for k,w in enumerate(chart_df['Скважина'][(chart_df['Пласт']==h) & (chart_df['Месторождение']==f)].unique()):
                    if (k==0) and (j%10==0):
                        fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                    mode='markers+lines',name=h,
                                    marker=dict(size=5,opacity=0.6), line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                    legendgrouptitle_text=f,legendgroup=f'horizont{j}'))
                    elif (k==0):
                        fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                    mode='markers+lines',name=h,
                                    marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                    legendgroup=f'horizont{j}'))
                    else:
                        fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                    mode='markers+lines',name=h, showlegend=False,
                                    marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                    legendgroup=f'horizont{j}'))
                    fig.update_layout(legend=dict(groupclick="togglegroup"))
    elif graph=='Точки':
        fig = go.Figure()
        for k,f in enumerate(chart_df['Месторождение'].unique()):
            for n,i in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                if n==0:
                    fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)],x=chart_df['Годы'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)], 
                                             mode='markers',name=i,
                                             marker=dict(size=10,opacity=0.6),
                                             legendgrouptitle_text=f,legendgroup=f'field{k}'))
                else:
                    fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)],x=chart_df['Годы'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)], 
                                            mode='markers',name=i,
                                            marker=dict(size=10,opacity=0.5),legendgroup=f'field{k}'))

        fig.update_layout(legend=dict(groupclick="toggleitem"))
    else:
        fig=px.box(chart_df,x="Годы",y=profil,color='Пласт')



    fig.add_trace(go.Scatter(x=np.arange(1,len(p90)+1),mode="lines+markers", y=p90,marker_symbol='0', marker_size=15,name='Факт P90',line=dict(width=5,color='red')))
    fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1),mode="lines+markers", y=p50,marker_symbol='0', marker_size=15,name='Факт P50',line=dict(width=5,color='yellow')))
    fig.add_trace(go.Scatter(x=np.arange(1,len(p10)+1),mode="lines+markers", y=p10,marker_symbol='0', marker_size=15,name='Факт P10',line=dict(width=5,color='mediumseagreen')))

    fig.update_layout(
        xaxis1=dict(title='Годы',range=[0.6,len(p10)+0.5]),
        yaxis1=dict(title=f"{label_dict[profil][0]} в год, {label_dict[profil][1]}"),
        title=dict(text=f'Сценарий 1-Обычные профиля, {label_dict[profil][0]}'))
    return fig

#------------------------------------------ГРАФИК УДЕЛЬНЫХ ПРОФИЛЕЙ-------------------------------------------------------------------
@app.callback(
    Output('udeln profils', 'figure'),
    [Input('field-selector', 'value'),
     Input('plast-selector', 'value'),
     Input('profil-selector','value'),
     Input('profil-rb','value'),
     Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac', 'n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff', 'n_clicks')]
)
def q_profils_udeln(field,plast,profil,graph,click_perm,click_nfrac,click_hoil,click_heff):
    chart_df=df[(df['Месторождение'].isin(field)) & (df['Пласт'].isin(plast))]
    ind=chart_df[chart_df['Годы'].isin(range(1,11))].index
    chart_df=chart_df.loc[ind] #целые значения по годам в дф
        #
    colors = px.colors.qualitative.Plotly[:len(chart_df['Пласт'].unique())]
    color_map = dict(zip(chart_df['Пласт'].unique(), colors))
    chart_df['Цвет пласт'] = chart_df['Пласт'].map(color_map)

    if profil not in ['ГФ, м3/т','Обв, %']: #профиля в списке не нормируем 
    #_____________________________________________________
        ctx = callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        if trigger_id:
            button_states = [click_perm,click_nfrac,click_hoil,click_heff]
            selected_buttons = [i for i, state in enumerate(button_states, start=1) if state % 2 != 0]
            if selected_buttons:
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                'Средняя эффективная мощность коллектора (ГИС)'] 
                divisor = df[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                chart_df[profil]=chart_df[profil] / divisor
    #_____________________________________________________
        if len(plast)!=0:
            p10=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=profil,
                aggfunc=[lambda x: np.percentile(x, 90)],margins=True,
                margins_name='P10').T['P10'].iloc[:-1].values

            p50=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=profil,
                aggfunc=[lambda x: np.percentile(x, 50)],margins=True,
                margins_name='P50').T['P50'].iloc[:-1].values

            p90=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=profil,
                aggfunc=[lambda x: np.percentile(x, 10)],margins=True,
                margins_name='P90').T['P90'].iloc[:-1].values
        else:
            p10,p50,p90=[],[],[]
        fig=go.Figure()
        if graph=='Профиля':
            for i,f in enumerate(chart_df['Месторождение'].unique()):
                for j,h in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    j=j+i*10
                    print(j)
                    for k,w in enumerate(chart_df['Скважина'][(chart_df['Пласт']==h) & (chart_df['Месторождение']==f)].unique()):
                        if (k==0) and (j%10==0):
                            fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6), line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgrouptitle_text=f,legendgroup=f'horizont{j}'))
                        elif (k==0):
                            fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'))
                        else:
                            fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h, showlegend=False,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'))
                            
                        fig.update_layout(legend=dict(groupclick="togglegroup"))
        elif graph=='Точки':
            fig = go.Figure()
            for k,f in enumerate(chart_df['Месторождение'].unique()):
                for n,i in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    if n==0:
                        fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)],x=chart_df['Годы'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)], 
                                                 mode='markers',name=i,
                                                 marker=dict(size=10,opacity=0.6),
                                                 legendgrouptitle_text=f,legendgroup=f'field{k}'))
                    else:
                        fig.add_trace(go.Scatter(y=chart_df[profil][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)],x=chart_df['Годы'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)], 
                                                mode='markers',name=i,
                                                marker=dict(size=10,opacity=0.5),legendgroup=f'field{k}'))

            fig.update_layout(legend=dict(groupclick="toggleitem"))
        else:
            fig=px.box(chart_df,x="Годы",y=profil,color='Пласт')
        
        fig.add_trace(go.Scatter(x=np.arange(1,len(p10)+1),mode="lines+markers", y=p10,marker_symbol='0', marker_size=15,name='Удельный факт P10',line=dict(width=5,color='mediumseagreen')))
        fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1),mode="lines+markers", y=p50,marker_symbol='0', marker_size=15,name='Удельный факт P50',line=dict(width=5,color='yellow')))
        fig.add_trace(go.Scatter(x=np.arange(1,len(p90)+1),mode="lines+markers", y=p90,marker_symbol='0', marker_size=15,name='Удельный факт P90',line=dict(width=5,color='red')))

        fig.update_layout(
            xaxis1=dict(title='Годы',range=[0.6,len(p10)+0.5]),
            yaxis1=dict(title=f'{label_dict[profil][0]+"".join([norm_mult[i] for i in selected_buttons])}'),
            title=dict(text=f'Сценарий 1-Удельные профиля, {label_dict[profil][0]}'))
        return fig
    else:
        fig=px.scatter()
        return fig

#------------------------------------------ГРАФИК ДИСКОНТИРОВАННЫХ ПРОФИЛЕЙ-------------------------------------------------------------------
@app.callback(
    Output('discont profils', 'figure'),
    [Input('field-selector', 'value'),
     Input('plast-selector', 'value'),
     Input('profil-selector', 'value'),
     Input('profil-rb','value'),
     Input('coef discont', 'value')#ввод значения коэф дисконтирования
    ]) 

def q_discont_udeln(field,plast,profil,graph,coef_discont):
    chart_df=df[(df['Месторождение'].isin(field)) & (df['Пласт'].isin(plast))]
    ind=chart_df[chart_df['Годы'].isin(range(1,11))].index
    chart_df=chart_df.loc[ind] #целые значения по годам в дф
    chart_df[f'{profil} дисконтирование']=chart_df[profil]*((1+coef_discont/100)**chart_df['Годы'])**(-1)
    #
    colors = px.colors.qualitative.Plotly[:len(chart_df['Пласт'].unique())]
    color_map = dict(zip(chart_df['Пласт'].unique(), colors))
    chart_df['Цвет пласт'] = chart_df['Пласт'].map(color_map)

    if profil not in ['ГФ, м3/т','Обв, %']:
        if len(plast)!=0:
            p10=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=f'{profil} дисконтирование', #расчет р50-дисконтир
                aggfunc=[lambda x: np.percentile(x, 90)],
                margins=True,
                margins_name='P10').T['P10'].iloc[:-1].values
            
            p50=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=f'{profil} дисконтирование',
                aggfunc=[lambda x: np.percentile(x, 50)],margins=True,
                margins_name='P50').T['P50'].iloc[:-1].values

            p90=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=f'{profil} дисконтирование',
                aggfunc=[lambda x: np.percentile(x, 10)],margins=True,
                margins_name='P90').T['P90'].iloc[:-1].values
            
        else: 
            p10,p50,p90=[],[],[]

        fig=go.Figure()
        if graph=='Профиля':
            for i,f in enumerate(chart_df['Месторождение'].unique()):
                for j,h in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    j=j+i*10
                    print(j)
                    for k,w in enumerate(chart_df['Скважина'][(chart_df['Пласт']==h) & (chart_df['Месторождение']==f)].unique()):
                        if (k==0) and (j%10==0):
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6), line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgrouptitle_text=f,legendgroup=f'horizont{j}'))
                        elif (k==0):
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'))
                        else:
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h, showlegend=False,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'))
                            
                        fig.update_layout(legend=dict(groupclick="togglegroup"))
        elif graph=='Точки':
            fig = go.Figure()
            for k,f in enumerate(chart_df['Месторождение'].unique()):
                for n,i in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    if n==0:
                        fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)],x=chart_df['Годы'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)], 
                                                 mode='markers',name=i,
                                                 marker=dict(size=10,opacity=0.6),
                                                 legendgrouptitle_text=f,legendgroup=f'field{k}'))
                    else:
                        fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)],x=chart_df['Годы'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)], 
                                                mode='markers',name=i,
                                                marker=dict(size=10,opacity=0.5),legendgroup=f'field{k}'))

            fig.update_layout(legend=dict(groupclick="toggleitem"))
        else:
            fig=px.box(chart_df,x="Годы",y=f'{profil} дисконтирование',color='Пласт')

        fig.add_trace(go.Scatter(x=np.arange(1,len(p10)+1),mode="lines+markers", y=p10,marker_symbol='0', marker_size=15,name='Диск. факт P10',line=dict(width=5,color='mediumseagreen')))
        fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1),mode="lines+markers", y=p50,marker_symbol='0', marker_size=15,name='Диск. факт P50',line=dict(width=5,color='yellow')))
        fig.add_trace(go.Scatter(x=np.arange(1,len(p90)+1),mode="lines+markers", y=p90,marker_symbol='0', marker_size=15,name='Диск. факт P90',line=dict(width=5,color='red')))

        #fig = px.scatter(chart_df,x="Годы",y=f'{profil} дисконтирование',color='Пласт',opacity=0.6)
        #fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1), y=p50,marker_symbol='x', marker_size=5,name='Диск. факт P50'))

        fig.update_layout(
            xaxis1=dict(title='Годы',range=[0.9,len(p10)+0.5]),
            yaxis1=dict(title=f'{label_dict[profil][0]} в год, {label_dict[profil][1]}'),
            title=dict(text=f'Диск. профиля, ставка {coef_discont}%'))
        return fig
    else:
        return px.scatter()

#-------------------------------------------ГРАФИК Удельных ДИСКОНТИРОВАННЫХ ПРОФИЛЕЙ----------------------------------------------------------
@app.callback(
    Output('udeln discont profils', 'figure'),
    [Input('field-selector', 'value'),
     Input('plast-selector', 'value'),
     Input('profil-selector', 'value'),
     Input('profil-rb','value'),
     Input('coef discont', 'value'),#ввод значения коэф дисконтирования
     Input('udeln perm', 'n_clicks'),
     Input('udeln nfrac', 'n_clicks'),
     Input('udeln hoil', 'n_clicks'),
     Input('udeln heff', 'n_clicks')]) 
def q_discont_udeln(field,horizon,profil,graph,coef_discont,click_perm,click_nfrac,click_hoil,click_heff):
    chart_df=df[(df['Месторождение'].isin(field)) & (df['Пласт'].isin(horizon))]
    ind=chart_df[chart_df['Годы'].isin(range(1,11))].index
    chart_df=chart_df.loc[ind] #целые значения по годам в дф
    chart_df[f'{profil} дисконтирование']=chart_df[profil]*((1+coef_discont/100)**chart_df['Годы'])**(-1)
    #
    colors = px.colors.qualitative.Plotly[:len(chart_df['Пласт'].unique())]
    color_map = dict(zip(chart_df['Пласт'].unique(), colors))
    chart_df['Цвет пласт'] = chart_df['Пласт'].map(color_map)

    if profil not in ['ГФ, м3/т','Обв, %']: #профиля в списке не нормируем 
    #_____________________________________________________
        ctx = callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        if trigger_id:
            button_states = [click_perm,click_nfrac,click_hoil,click_heff]
            selected_buttons = [i for i, state in enumerate(button_states, start=1) if state % 2 != 0]
            if selected_buttons:
                divisor_cols = ['Средняя проницаемость (ГИС)','Число стадий', 
                                'Средняя эффективная нефтенасыщенная мощность коллектора (ГИС)', 
                                'Средняя эффективная мощность коллектора (ГИС)'] 
                divisor = df[divisor_cols].iloc[:, [btn - 1 for btn in selected_buttons]].product(axis=1) #Перемножаем значения в выбранных столбцах
                chart_df['{profil} дисконтирование']=chart_df['{profil} дисконтирование'] / divisor

        if len(horizon)!=0:
            p10=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=f'{profil} дисконтирование', #расчет р50-дисконтир
                aggfunc=[lambda x: np.percentile(x, 90)],
                margins=True,
                margins_name='P10').T['P10'].iloc[:-1].values
            
            p50=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=f'{profil} дисконтирование',
                aggfunc=[lambda x: np.percentile(x, 50)],margins=True,
                margins_name='P50').T['P50'].iloc[:-1].values

            p90=pd.pivot_table(chart_df,index='Скважина',columns='Годы',values=f'{profil} дисконтирование',
                aggfunc=[lambda x: np.percentile(x, 10)],margins=True,
                margins_name='P90').T['P90'].iloc[:-1].values
        else:
            p10,p50,p90=[],[],[]

        fig=go.Figure()
        if graph=='Профиля':
            for i,f in enumerate(chart_df['Месторождение'].unique()):
                for j,h in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    j=j+i*10
                    print(j)
                    for k,w in enumerate(chart_df['Скважина'][(chart_df['Пласт']==h) & (chart_df['Месторождение']==f)].unique()):
                        if (k==0) and (j%10==0):
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6), line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgrouptitle_text=f,legendgroup=f'horizont{j}'))
                        elif (k==0):
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'))
                        else:
                            fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)],x=chart_df['Годы'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)], 
                                        mode='markers+lines',name=h, showlegend=False,
                                        marker=dict(size=5,opacity=0.6),line=dict(width=1,color=chart_df['Цвет пласт'][(chart_df['Скважина']==w) & (chart_df['Пласт']==h)].values[0]),
                                        legendgroup=f'horizont{j}'))
                            
                        fig.update_layout(legend=dict(groupclick="togglegroup"))
        elif graph=='Точки':
            fig = go.Figure()
            for k,f in enumerate(chart_df['Месторождение'].unique()):
                for n,i in enumerate(chart_df['Пласт'][chart_df['Месторождение']==f].unique()):
                    if n==0:
                        fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)],x=chart_df['Годы'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)], 
                                                 mode='markers',name=i,
                                                 marker=dict(size=10,opacity=0.6),
                                                 legendgrouptitle_text=f,legendgroup=f'field{k}'))
                    else:
                        fig.add_trace(go.Scatter(y=chart_df[f'{profil} дисконтирование'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)],x=chart_df['Годы'][(chart_df['Пласт']==i) & (chart_df['Месторождение']==f)], 
                                                mode='markers',name=i,
                                                marker=dict(size=10,opacity=0.5),legendgroup=f'field{k}'))

            fig.update_layout(legend=dict(groupclick="toggleitem"))
        else:
            fig=px.box(chart_df,x="Годы",y=f'{profil} дисконтирование',color='Пласт')

        fig.add_trace(go.Scatter(x=np.arange(1,len(p10)+1),mode="lines+markers", y=p10,marker_symbol='0', marker_size=15,name='Диск. удельн. факт P10',line=dict(width=5,color='mediumseagreen')))
        fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1),mode="lines+markers", y=p50,marker_symbol='0', marker_size=15,name='Диск. удельн. факт P50',line=dict(width=5,color='yellow')))
        fig.add_trace(go.Scatter(x=np.arange(1,len(p90)+1),mode="lines+markers", y=p90,marker_symbol='0', marker_size=15,name='Диск. удельн. факт P90',line=dict(width=5,color='red')))

        #fig = px.scatter(chart_df,x="Годы",y=f'{profil} дисконтирование',color='Пласт',opacity=0.6)
        #fig.add_trace(go.Scatter(x=np.arange(1,len(p50)+1), y=p50,marker_symbol='x', marker_size=5,name='Диск. удельн. факт P50'))

        fig.update_layout(
            xaxis1=dict(title='Годы',range=[0.9,len(p10)+0.5]),
            yaxis1=dict(title=f'{label_dict[profil][0]+"".join([norm_mult[i] for i in selected_buttons])}'),
            title=dict(text=f'Диск. удельные профиля, ставка {coef_discont}%'))
        return fig
    else:
        return px.scatter()
#-------------------------------------------калбэк для графиков ТАБ2------------------------------------------------------------------------
#------------------------------------------ГИСТОГРАММА Параметров заканчивания---*----------------------------------------------------------
@app.callback(
    Output('wellcomp histogram tab2', 'figure'),
    [Input('field-selector', 'value'),
     Input('plast-selector', 'value'),
     Input('variable-selector', 'value'),
     Input('rb_hist_tab2','value')]
)
def qstart_histogram(field,horizon,param,grup):
    chart_df=df[(df['Месторождение'].isin(field)) & (df['Пласт'].isin(horizon))]
    #chart_df=chart_df.loc[chart_df['Годы']==year] #фильтр года
    chart_df = chart_df.drop_duplicates(subset=['Скважина'])

    grup_dict={'По кластерам':'Кластер','По месторождениям':'Месторождение','По пластам':'Пласт','По скважинам':'Скважина'}

    pivot_chart_df=pd.pivot_table(chart_df,index=grup_dict[grup],values=param)
    pivot_chart_df[grup_dict[grup]]=pivot_chart_df.index
    fig = px.bar(pivot_chart_df,y=param,x=grup_dict[grup],color=grup_dict[grup],opacity=0.6)
    return fig

#-------------------------------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__': # Run the app
    app.run(debug=True)
