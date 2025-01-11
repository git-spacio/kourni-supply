import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime


# Simple password protection
def check_password():
    def password_entered():
        if st.session_state["password"] == "2010spacioinventarios.":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("Password incorrect")
        return False
    else:
        return True

if check_password():
    # Cargar todos los dataframes
    df_pt = pd.read_csv('/home/snparada/Spacionatural/Data/Historical/Supply/pt_stockout_categories_by_day.csv')
    df_me_mp = pd.read_csv('/home/snparada/Spacionatural/Data/Historical/Supply/me_mp_stockout_categories_by_day.csv')
    df_sales = pd.read_csv('/home/snparada/Spacionatural/Data/Historical/Finance/historic_sales_by_day_UF.csv')
    df_inventory = pd.read_csv('/home/snparada/Spacionatural/Data/Historical/Finance/inventory_value_in_time.csv')

    # Preparar datos de ventas
    df_sales['issuedDate'] = pd.to_datetime(df_sales['issuedDate'])
    df_sales['year'] = df_sales['issuedDate'].dt.year
    df_sales['month'] = df_sales['issuedDate'].dt.month
    
    # Agregar ventas por mes y año (cambiado a totals_net_uf)
    monthly_sales = df_sales.groupby(['year', 'month'])['totals_net_uf'].sum().reset_index()
    monthly_sales['date'] = monthly_sales.apply(lambda x: datetime(int(x['year']), int(x['month']), 1), axis=1)

    # Preparar datos de inventario
    df_inventory['fecha'] = pd.to_datetime(df_inventory['fecha'])

    # Crear pestañas
    tab1, tab2, tab3 = st.tabs(["Gestión de Inventario", "Valorización", "Inventario/Ventas"])

    # Pestaña de Gestión de Inventario
    with tab1:
        st.title('Gestión del Inventario')
        
        # Filtros solo para la gestión de inventario
        with st.sidebar:
            st.title('Navegación')
            option = st.selectbox('Selecciona tipo de producto a ver', ('PT', 'ME-MP'))
            selected_warehouse = st.multiselect('Selecciona la Ubicación', 
                                              df_pt['warehouse'].unique(),
                                              default=['FV/E-Commerce'])
            selected_category = st.multiselect('Categoría de Productos', 
                                             df_pt['category'].unique(),
                                             default=['Global'])

        # Filter data based on selection
        if option == 'PT':
            df = df_pt
        else:
            df = df_me_mp

        if selected_warehouse:
            df = df[df['warehouse'].isin(selected_warehouse)]
        if selected_category:
            df = df[df['category'].isin(selected_category)]

        # Create line chart
        chart = alt.Chart(df).mark_line().encode(
            x='date:T',
            y='%stockout:Q',
            color='category:N',
            tooltip=['date', 'warehouse', 'category', '%stockout']
        ).interactive()

        st.altair_chart(chart, use_container_width=True)

        # Display data based on selection
        st.header(f'{option} Data de Inventario')
        latest_date = df['date'].max()
        df_lastest = df[df['date'] == latest_date]
        st.dataframe(df_lastest)

    # Pestaña de Valorización
    with tab2:
        st.title('Valorización de Ventas en UF')
        
        # Filtro de años
        available_years = sorted(df_sales['year'].unique())
        selected_years = st.multiselect(
            'Seleccionar Años',
            options=available_years,
            default=[2023, 2024]  # Preseleccionar 2023 y 2024
        )
        
        # Filtrar datos por años seleccionados
        filtered_monthly_sales = monthly_sales[monthly_sales['year'].isin(selected_years)]
        
        # Crear gráfico de ventas en UF con datos filtrados
        sales_chart = alt.Chart(filtered_monthly_sales).mark_line().encode(
            x=alt.X('month:O', 
                   title='Mes',
                   axis=alt.Axis(labelAngle=0)),
            y=alt.Y('totals_net_uf:Q', 
                   title='Ventas (UF)',
                   axis=alt.Axis(format=',.2f')),
            color=alt.Color('year:N', title='Año')
        ).properties(
            width=800,
            height=400
        ).configure_axis(
            labelFontSize=12,
            titleFontSize=14
        ).interactive()

        st.altair_chart(sales_chart)

        # Mostrar tabla de datos filtrados
        st.header('Datos de Ventas Mensuales en UF')
        st.dataframe(filtered_monthly_sales.sort_values(['year', 'month'], ascending=[False, True]))

    # Pestaña de Inventario/Ventas
    with tab3:
        st.title('Ratio Inventario/Ventas')
        
        # Slider para seleccionar número de días
        num_days = st.slider('Número de días para el cálculo', 30, 180, 90)
        
        # Función para calcular ventas de los últimos n días
        def calculate_trailing_sales(row_date, days):
            end_date = row_date
            start_date = end_date - pd.Timedelta(days=days)
            mask = (df_sales['issuedDate'] >= start_date) & (df_sales['issuedDate'] < end_date)
            total_sales = df_sales.loc[mask, 'totals_net'].sum()
            return total_sales
        
        # Calcular ventas móviles para cada fecha de inventario
        df_ratio = df_inventory.copy()
        df_ratio[f'{num_days}_days'] = df_ratio['fecha'].apply(
            lambda x: calculate_trailing_sales(x, num_days)
        )
        
        # Calcular ratio y multiplicar por 100
        df_ratio['ratio'] = (df_ratio['total'] / df_ratio[f'{num_days}_days'] * 100).round(1)
        
        # Crear gráfico del ratio
        ratio_chart = alt.Chart(df_ratio).mark_line().encode(
            x=alt.X('fecha:T', 
                   title='Fecha',
                   axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('ratio:Q', 
                   title=f'Ratio Inventario/Ventas % ({num_days} días)',
                   axis=alt.Axis(format=',.1f')),
            tooltip=[
                alt.Tooltip('fecha:T', title='Fecha'),
                alt.Tooltip('total:Q', title='Inventario', format=',.0f'),
                alt.Tooltip(f'{num_days}_days:Q', title='Ventas', format=',.0f'),
                alt.Tooltip('ratio:Q', title='Ratio %', format=',.1f')
            ]
        ).properties(
            width=800,
            height=400
        ).interactive()

        st.altair_chart(ratio_chart)

        # Crear gráfico del valor del inventario
        inventory_chart = alt.Chart(df_ratio).mark_line().encode(
            x=alt.X('fecha:T', 
                   title='Fecha',
                   axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('total:Q', 
                   title='Valor del Inventario',
                   axis=alt.Axis(format=',.0f')),
            tooltip=[
                alt.Tooltip('fecha:T', title='Fecha'),
                alt.Tooltip('total:Q', title='Valor del Inventario', format=',.0f')
            ]
        ).properties(
            width=800,
            height=400
        ).interactive()

        st.header('Valor del Inventario en el Tiempo')
        st.altair_chart(inventory_chart)