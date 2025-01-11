import sys
import pandas as pd
from datetime import timedelta
sys.path.append('/home/snparada/Spacionatural/Libraries')
from sheets_lib.main_sheets import GoogleSheets

# Rutas
gs_sheet = GoogleSheets('1qXFVi8WoyBnfxmsrUZ6BmB5gvIHU8oocbSVUkGEtcGY')
df_sales = pd.read_csv('/home/snparada/Spacionatural/Data/Historical/Finance/historic_sales_with_items.csv', low_memory=False, usecols={'issuedDate','items_product_sku','sales_channel','items_quantity'})
df_pivot = pd.read_csv('/home/snparada/Spacionatural/Data/Recent/stocks_by_location.csv', low_memory=False)
df_bombs = pd.read_csv('/home/snparada/Spacionatural/Data/Dim/Odoo/all_boms.csv')
df_products = pd.read_csv('/home/snparada/Spacionatural/Data/Dim/Odoo/all_products.csv', low_memory=False, usecols={'id','default_code','all_product_tag_ids','categ_id'})

# Convertir columnas usadas para merge a tipo string
df_sales['items_product_sku'] = df_sales['items_product_sku'].astype(str)
df_pivot['internal_reference'] = df_pivot['internal_reference'].astype(str)
df_bombs['manufactured_product_sku'] = pd.to_numeric(df_bombs['manufactured_product_sku'], errors='coerce')
df_bombs['manufactured_product_sku'] = df_bombs['manufactured_product_sku'].fillna(0).astype(int).astype(str)
df_bombs['component_product_sku'] = df_bombs['component_product_sku'].astype(str)
df_products['id'] = df_products['id'].astype(str)
df_products['default_code'] = df_products['default_code'].astype(str)
# Procesar la columna category_id para extraer la información dentro de las comillas
df_products['categ_id'] = df_products['categ_id'].apply(lambda x: eval(x)[1] if isinstance(eval(x), list) and len(eval(x)) > 1 else '')



"""
1. Extracting and Processing Sales Data
"""

# Convertir issuedDate a formato datetime en el archivo de ventas
df_sales['issuedDate'] = pd.to_datetime(df_sales['issuedDate'])

# Filtrar las ventas de hace un año, sumando 40 días (esto será dinámico)
today = pd.to_datetime('today').normalize()
start_period = today - timedelta(days=365)
end_period = start_period + timedelta(days=100)

# Filtrar las ventas entre esas fechas
df_filtered_sales = df_sales[(df_sales['issuedDate'] >= start_period) & (df_sales['issuedDate'] <= end_period)]

# Agrupar las ventas por producto (SKU) y canal de ventas, sumando las cantidades vendidas
df_sales_summary = df_filtered_sales.groupby(['items_product_sku', 'sales_channel'])['items_quantity'].sum().reset_index()
df_sales_summary['items_quantity'] = (df_sales_summary['items_quantity']/3).round(0)

# Renombrar las columnas para que coincidan con el inventario
df_sales_summary.rename(columns={'items_product_sku': 'internal_reference', 'sales_channel': 'sales_channel', 'items_quantity': 'total_units_sold'}, inplace=True)

# Pivotear los datos para que cada canal de ventas sea una columna
df_sales_pivot = df_sales_summary.pivot_table(index='internal_reference', 
                                              columns='sales_channel', 
                                              values='total_units_sold', 
                                              aggfunc='sum', 
                                              fill_value=0).reset_index()

# Renombrar las columnas de ventas pivotadas (ajustando nombres como ejemplo)
df_sales_pivot.columns.name = None

"""
2. Merging Sales and separate the df's
"""

# Merge con df_pivot (datos de inventario)
df_final = pd.merge(df_pivot, df_sales_pivot, on='internal_reference', how='left')

# Assuming df_pivot has a 'tags' column
df_final['tags'] = df_pivot['tags']

# Filter data based on tags
df_pt = df_final[df_final['tags'] == 'PT'].copy()
df_me_mp = df_final[df_final['tags'].isin(['ME', 'MP'])].copy()

# Rename columns (use 'Nombre' instead of 'product_name')
df_pt.rename(columns={'internal_reference': 'SKU', 'product_name': 'Nombre'}, inplace=True)
df_me_mp.rename(columns={'internal_reference': 'SKU', 'product_id': 'Nombre'}, inplace=True)

# Calculate Total (use .loc to avoid SettingWithCopyWarning)
df_pt.loc[:, 'Demanda Total'] = df_pt['Cotizaciones'] + df_pt['E-Commerce'] + df_pt['Mercado Libre'] + df_pt['Tienda Sabaj']

df_me_mp = df_me_mp[['SKU', 'Nombre', 'tags', 'JS/Materia Prima y Envases']]


"""
 3. Adding the BOM list
"""

df_bombs = df_bombs[df_bombs['name'] == 'MP']

# Merge df_bombs with df_me_mp to get the available quantities of MP
df_bombs = df_bombs.merge(df_me_mp[['SKU', 'JS/Materia Prima y Envases']], left_on='component_product_sku', right_on='SKU', how='left')


df_bombs['max_quantity'] = df_bombs['JS/Materia Prima y Envases'] // df_bombs['quantity_needed']



# Merge the max quantities back to df_pt
df_pt['SKU'] = df_pt['SKU'].astype(str)
df_pt = df_pt.merge(df_bombs[['max_quantity','manufactured_product_sku']], left_on='SKU', right_on='manufactured_product_sku', how='left')

# Rename the 'max_quantity' column to 'Max_Fabricable'
df_pt.rename(columns={'max_quantity': 'Max_Fabricable'}, inplace=True)

df_pt.loc[:, 'Cantidad Picking'] = df_pt['E-Commerce'] + df_pt['Mercado Libre']

df_pt.loc[:, 'Cantidad Sabaj'] = df_pt['Cotizaciones'] + df_pt['Tienda Sabaj']
# Fusionar df_final con df_products para obtener la información de categoría
df_pt = pd.merge(df_pt, df_products[['default_code', 'categ_id']], left_on='SKU', right_on='default_code', how='left')

# Renombrar la columna category_id
df_pt.rename(columns={'categ_id': 'Familia'}, inplace=True)

df_pt = df_pt[['SKU', 'product_id', 'Familia', 'Max_Fabricable', 'Demanda Total', 'Cantidad Picking', 'Cantidad Sabaj' , 'FV/Stock', 'MELIF/Stock', 'FV/E-Commerce', 'FV/ML/Stock', 'JS/Stock', 'Cotizaciones', 'E-Commerce', 'Mercado Libre', 'Tienda Sabaj']]


"""
4. Uploading the data
"""

# Asegurarse de que todas las columnas necesarias estén presentes en df_pt
required_columns = ['SKU', 'product_id', 'Familia', 'Max_Fabricable', 'Demanda Total', 'Cantidad Picking', 'Cantidad Sabaj', 'FV/Stock', 'MELIF/Stock', 'FV/E-Commerce', 'FV/ML/Stock', 'JS/Stock', 'Cotizaciones', 'E-Commerce', 'Mercado Libre', 'Tienda Sabaj']

missing_columns = [col for col in required_columns if col not in df_pt.columns]
if missing_columns:
    print(f"Warning: The following columns are missing in df_pt: {missing_columns}")
    # Puedes decidir cómo manejar las columnas faltantes, por ejemplo:
    # for col in missing_columns:
    #     df_pt[col] = 0  # o algún otro valor predeterminado

# Seleccionar solo las columnas disponibles
available_columns = [col for col in required_columns if col in df_pt.columns]
df_pt = df_pt[available_columns]

# Update the respective sheets
gs_sheet.update_all_data_by_dataframe(df_pt, 'PT')
gs_sheet.update_all_data_by_dataframe(df_me_mp, 'ME-MP')
