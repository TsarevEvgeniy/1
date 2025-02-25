import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import datetime as dt
import io
import base64
import calendar

# Подключаем кастомный CSS для фона и шрифта
st.markdown("""
    <style>
        body {background: #f2bc62;}
    </style>
""", unsafe_allow_html=True)

# Титульный лист
st.title("Аналитическая панель автономной некомерческой организации Простые вещи")

st.markdown(
    "<p style='font-size:14px; font-weight:bold;'>"
    "Аналитическая панель создана для АНО Простые вещи в рамках презентации работы мастерской Яндекс. "
    "Практикум и включает в себя когортный и RFM-анализ, анализ платежей и анализ пользователей. "
    "Для перехода между страницами используйте меню слева."
    "</p>",
    unsafe_allow_html=True
)

# Кнопка для загрузки файла
uploaded_file = st.file_uploader("Загрузите файл с данными (например, CSV или Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        data = pd.read_csv(uploaded_file)
    else:
        data = pd.read_excel(uploaded_file, engine='openpyxl')
    
    st.write("Загруженные данные:")
    st.dataframe(data.head())
    
    data = data[data["status"] != "Отклонена"]
    data["aim"] = data["aim"].replace("Вещи с особенностями", "Пожертвование на ведение уставной деятельности")
    data["aim"] = data["aim"].fillna("Не определен")
    data = data.dropna(subset=["customer"])
    data["order_id"] = data["order_id"].fillna("-")
    
    data['action_date'] = pd.to_datetime(data['action_date'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    data = data.dropna(subset=['action_date'])

    if st.sidebar.button('Общая информация о пожертвованиях'):
        st.write("Обработанные данные о пожертвованиях:")
        st.dataframe(data.head())
        
        # График топ-10 клиентов по сумме платежей
        customer_sums = data.groupby("customer")["final_sum"].sum().sort_values(ascending=False).head(10)
        plt.figure(figsize=(12, 6))
        bars = plt.barh(customer_sums.index, customer_sums.values, color="skyblue", edgecolor="black")
        plt.xlabel("Сумма платежей (final_sum)", fontsize=12)
        plt.ylabel("Клиент (customer)", fontsize=12)
        plt.title("Топ-10 клиентов по сумме платежей", fontsize=14, fontweight="bold")
        plt.xticks(fontsize=10)
        plt.yticks(fontsize=10)
        plt.gca().invert_yaxis()
        for bar in bars:
            plt.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f"{bar.get_width():,.0f}",
                     va="center", ha="left", fontsize=10, color="black")
        plt.grid(axis="x", linestyle="--", alpha=0.7)
        st.pyplot(plt)

        # График динамики выручки по месяцам
        data['month'] = data['action_date'].dt.to_period('M')
        monthly_revenue = data.groupby('month')['final_sum'].sum()
        plt.figure(figsize=(10, 6))
        monthly_revenue.plot(kind='bar', color='skyblue', edgecolor='black')
        plt.title('Динамика выручки по месяцам')
        plt.xlabel('Месяц')
        plt.ylabel('Выручка (₽)')
        plt.xticks(rotation=45)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        st.pyplot(plt)

    if st.sidebar.button('RFM анализ'):
        temp = ['customer', 'order_id', 'action_date', 'final_sum']
        rfm_data = data[temp]

        # Отключаем предупреждения
        pd.options.mode.chained_assignment = None

        # Устанавливаем текущую дату для анализа
        NOW = dt.datetime(2025, 1, 31)

        # Преобразуем столбец с датой в datetime формат
        rfm_data['action_date'] = pd.to_datetime(rfm_data['action_date'])

        # Создаём таблицу для RFM анализа
        rfm_table = rfm_data.groupby('customer').agg({
            'action_date': lambda x: (NOW - x.max()).days,  # Recency
            'order_id': lambda x: len(x.unique()),  # Frequency
            'final_sum': lambda x: x.sum()  # Monetary
        })

        # Преобразуем Recency в целое число
        rfm_table['action_date'] = rfm_table['action_date'].astype(int)

        # Переименовываем столбцы
        rfm_table.rename(columns={'action_date': 'recency',
                                   'order_id': 'frequency',
                                   'final_sum': 'monetary_value'}, inplace=True)

        # Вычисляем квантили для сегментации
        quantiles = rfm_table.quantile(q=[0.33, 0.67])
        quantiles = quantiles.to_dict()

        # Функции для сегментации
        def R_Class(x, p, d):
            if x <= d[p][0.33]:
                return 3
            elif x <= d[p][0.67]:
                return 2
            else:
                return 1

        def FM_Class(x, p, d):
            if x <= d[p][0.33]:
                return 1
            elif x <= d[p][0.67]:
                return 2
            else:
                return 3

        # Применяем сегментацию по каждому квартилю
        rfm_Segment = rfm_table.copy()
        rfm_Segment['R_Quartile'] = rfm_Segment['recency'].apply(R_Class, args=('recency', quantiles,))
        rfm_Segment['F_Quartile'] = rfm_Segment['frequency'].apply(FM_Class, args=('frequency', quantiles,))
        rfm_Segment['M_Quartile'] = rfm_Segment['monetary_value'].apply(FM_Class, args=('monetary_value', quantiles,))

        # Формируем итоговый RFM
        rfm_Segment['rfm'] = rfm_Segment.R_Quartile.map(str) + rfm_Segment.F_Quartile.map(str) + rfm_Segment.M_Quartile.map(str)

        # 
        rfm_Segment = rfm_Segment.reset_index()

        # Мержим с исходными данными
        data = data.merge(rfm_Segment[['customer', 'rfm']], on='customer', how='left')

        # Функция для категоризации клиентов
        list_klient = {
            'Ушедшие клиенты': ['111', '112', '113', '121', '122', '123', '131', '132', '133'],
            'Неактивные клиенты': ['211', '212', '213', '221', '222', '223', '231', '232', '233'],
            'Постоянные клиенты': ['311', '312', '313', '321', '322', '323', '331', '332', '333']
        }
        
        #Add comment
        #Add comment 2
        #Add comment 3

        def categor_klient(rfm):
            for klient, items_klient in list_klient.items():
                for item in items_klient:
                    if item in rfm:
                        return klient
            return 'Неопределённый'  # Если клиент не попал в категорию

        data['categor_klient'] = data['rfm'].apply(categor_klient)

        # Группируем по RFM и считаем статистики
        rfm_summary = data.groupby('rfm').agg(
        people_count=('id', 'count'),  # Количество людей с данным rfm
        avg_payment=('final_sum', 'mean'),  # Средний платеж
        total_donations=('final_sum', 'sum')  # Общая сумма пожертвований
        ).reset_index()

        # Округляем суммы для удобства
        rfm_summary['avg_payment'] = rfm_summary['avg_payment'].round(2)
        rfm_summary['total_donations'] = rfm_summary['total_donations'].round(2)

        rfm_summary = rfm_summary.rename(columns={
        'people_count': 'Количество человек',
        'avg_payment': 'Средний платеж',
        'total_donations': 'Общая сумма пожертвований'
        })

        # Функция для создания мини-гистограммы
        def create_mini_histogram(data):
            fig, ax = plt.subplots(figsize=(6, 1))  # Увеличиваем ширину графика

            months = data.index  # Получаем номера месяцев
            month_labels = [calendar.month_abbr[m][0] for m in months]  # Берём первую букву месяца

            ax.bar(months, data.values, color='blue', alpha=0.7, edgecolor="black", width=0.6)  # Разрывы между столбцами
            ax.set_xticks(months)
            ax.set_xticklabels(month_labels, fontsize=8)  # Добавляем подписи (первая буква месяца)
    
            ax.set_yticks([])
            ax.set_frame_on(False)

            buf = io.BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.1)
            plt.close(fig)
    
            buf.seek(0)
            encoded = base64.b64encode(buf.read()).decode("utf-8")
            return f'<img src="data:image/png;base64,{encoded}" width="120"/>'

        # Добавляем мини-гистограммы в RFM-таблицу
        rfm_summary['Гистограмма платежей'] = rfm_summary['rfm'].apply(
        lambda x: create_mini_histogram(data[data['rfm'] == x].groupby(data['action_date'].dt.month)['final_sum'].sum())
        )

        # Конвертируем DataFrame в HTML-таблицу с графиками
        table_html = rfm_summary[['rfm', 'Количество человек', 'Средний платеж', 'Общая сумма пожертвований', 'Гистограмма платежей']].to_html(escape=False, index=False)

        # Отображаем таблицу через markdown
        st.markdown(table_html, unsafe_allow_html=True)

        # Скачать RFM таблицу
        csv = rfm_Segment.to_csv(index=False).encode('utf-8')
        st.download_button("Скачать RFM-таблицу", data=csv, file_name='rfm_analysis.csv', mime='text/csv')

    if st.sidebar.button('Когортный анализ'):
        data["cohort"] = data.groupby("customer")["action_date"].transform("min").dt.to_period("M")
        data["cohort_index"] = (data["action_date"].dt.to_period("M") - data["cohort"]).apply(lambda x: x.n if pd.notna(x) else None).astype("Int64")
        cohort_table = data.groupby(["cohort", "cohort_index"])['customer'].nunique().unstack().fillna(0)
        
        cohort_size = cohort_table.iloc[:, 0]
        retention_matrix = cohort_table.divide(cohort_size, axis=0).round(3) * 100

        # ARPU (средняя выручка на пользователя)
        revenue_table = data.groupby(["cohort", "cohort_index"])["operation_sum"].sum().unstack().fillna(0)

        # Исправленный расчет ARPU с использованием reindex для предотвращения деления на ноль
        arpu_matrix = revenue_table.div(cohort_size.reindex(revenue_table.columns, fill_value=1), axis=1).round(2)

        # Lifetime Value (LTV)
        ltv_matrix = (arpu_matrix.cumsum()).round(2)
        
        st.write("Когортный анализ - Retention Rate:")
        st.dataframe(retention_matrix)
        
        plt.figure(figsize=(10, 6))
        sns.heatmap(retention_matrix, annot=True, fmt=".1f", cmap="Blues")
        plt.title("Когортный анализ: удержание клиентов (%)")
        plt.xlabel("Месяц после первого пожертвования")
        plt.ylabel("Когорта (месяц первого пожертвования)")
        st.pyplot(plt)

        # Визуализация ARPU (график)
        plt.figure(figsize=(10, 6))
        arpu_matrix.mean(axis=0).plot(marker="o", linestyle="-")
        plt.title("Средняя выручка на пользователя (ARPU) по месяцам")
        plt.xlabel("Месяц после первого пожертвования")
        plt.ylabel("ARPU")
        st.pyplot(plt)

        # Визуализация LTV (график)
        plt.figure(figsize=(10, 6))
        ltv_matrix.mean(axis=0).plot(marker="o", linestyle="-")
        plt.title("Lifetime Value (LTV) по месяцам")
        plt.xlabel("Месяц после первого пожертвования")
        plt.ylabel("LTV")
        st.pyplot(plt)