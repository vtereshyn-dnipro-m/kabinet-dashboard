# pages/3_Forecast.py
import streamlit as st
from db.connection import run_query

st.title("Прогноз")
st.caption("Прогноз спроса и рекомендации по дозаказу")

query = """
    SELECT
        sku,
        warehouse_name,
        quantity AS current_stock,
        avg_daily_sales,
        lead_time_days,
        ROUND(quantity / NULLIF(avg_daily_sales, 0), 1) AS days_of_stock,
        suggested_qty,
        status,
        created_at
    FROM kabinet_data.draft_orders
    ORDER BY created_at DESC
"""

try:
    df = run_query(query)
    if not df.empty:
        at_risk = df[df["days_of_stock"] < df["lead_time_days"]]
        st.metric("Товаров в зоне риска", len(at_risk),
                  help="Запаса меньше, чем время поставки — успеть дозаказать")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("🔜 Раздел готовится: ждёт подключения данных продаж.")
        st.markdown("""
        **Как это будет работать:**

        | Что | Откуда |
        |---|---|
        | Скорость продаж (шт/день) | продажи Amazon из `dnipro_m` |
        | Days of cover | остаток ÷ скорость продаж |
        | Зона риска | запаса меньше, чем срок поставки |
        | Рекомендация дозаказа | суммой на N дней вперёд с учётом поставок в пути |

        Остатки уже собираются ежедневно — как только подключим продажи,
        прогноз включится автоматически.
        """)
except Exception as e:
    st.error(f"Не удалось загрузить прогноз: {e}")
