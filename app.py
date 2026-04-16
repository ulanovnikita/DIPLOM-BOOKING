import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
st.set_page_config(page_title="Система бронирования", layout="wide") # Желательно добавить wide layout

st.markdown("""
    <style>
    .stButton>button {
        border-radius: 10px;
        transition: 0.3s;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ---
# ВСТАВЬ СВОИ ДАННЫЕ ТУТ:
URL = "https://ufmtkugrcxafegopaqql.supabase.co"
KEY = "sb_publishable_4lYFZSz4hxEHX51CHC0fzQ_jqDT-hIK"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="Система Бронирования", layout="wide", page_icon="🏢")

# --- 2. БОКОВАЯ ПАНЕЛЬ (АВТОРИЗАЦИЯ) ---
st.sidebar.header("🔐 Вход в систему")
user_email = st.sidebar.text_input("Ваш Email", placeholder="example@mail.ru")
user_password = st.sidebar.text_input("Пароль", type="password")

access_granted = False

if user_email and user_password:
    # 1. Сначала проверяем, есть ли такой пользователь в базе
    user_query = supabase.table("users").select("*").eq("email", user_email).execute()
    
    if len(user_query.data) == 0:
        # Если пользователя нет - предлагаем регистрацию
        st.sidebar.info("✨ Похоже, вы у нас впервые!")
        if st.sidebar.button("Зарегистрироваться"):
            if len(user_password) < 6:
                st.sidebar.error("❌ Пароль должен быть от 6 символов!")
            else:
                supabase.table("users").insert({"email": user_email, "password": user_password}).execute()
                # Логируем регистрацию для аудита
                supabase.table("audit_logs").insert({"user_email": user_email, "action": "Регистрация нового пользователя"}).execute()
                st.sidebar.success("✅ Регистрация успешна! Теперь введите пароль снова для входа.")
    else:
        # 2. Если пользователь есть - сверяем пароль
        db_password = user_query.data[0]['password']
        if user_password == db_password:
            st.sidebar.success(f"✅ Доступ разрешен: {user_email}")
            access_granted = True
        else:
            st.sidebar.error("❌ Неверный пароль!")

# --- 3. ОСНОВНОЙ ИНТЕРФЕЙС ---
if access_granted:
    st.title("🏢 Система бронирования рабочих пространств")
    
   # Базовое меню для обычных пользователей
    menu = ["📍 Забронировать", "📅 Мои бронирования"]
    
    # ПРОВЕРКА НА АДМИНИСТРАТОРА
    # 
    if user_email == "ulanovadmin@gmail.com":
        menu.append("🛡️ Журнал аудита")
        st.sidebar.success("👑 Вы вошли как Администратор")

    choice = st.sidebar.selectbox("Навигация", menu)

    if choice == "📍 Забронировать":
        st.subheader("Доступные помещения")
        rooms = supabase.table("rooms").select("*").execute()
        
        # Визуальные карточки комнат
        cols = st.columns(len(rooms.data))
        for i, room in enumerate(rooms.data):
            with cols[i]:
                st.info(f"### {room['name']}")
                st.write(f"👥 Вместимость: **{room['capacity']}** чел.")
        
        st.divider()
        
        # Форма записи
        with st.form("booking_form"):
            room_names = {r['name']: r['id'] for r in rooms.data}
            selected_room = st.selectbox("Выберите комнату", list(room_names.keys()))
            date = st.date_input("Дата", min_value=datetime.today())
            t1 = st.time_input("Начало", value=datetime.strptime("09:00", "%H:%M"))
            t2 = st.time_input("Конец", value=datetime.strptime("10:00", "%H:%M"))
            
            submit = st.form_submit_button("Подтвердить бронирование")
            
            if submit:
                start_dt = f"{date} {t1}"
                end_dt = f"{date} {t2}"
                room_id = room_names[selected_room]

                # Проверка конфликтов
                check = supabase.table("bookings").select("*").eq("room_id", room_id).filter("start_time", "lt", end_dt).filter("end_time", "gt", start_dt).execute()

                if len(check.data) > 0:
                    st.error("❌ Это время уже занято!")
                elif t1 >= t2:
                    st.error("❌ Некорректное время!")
                else:
                    # Запись брони
                    supabase.table("bookings").insert({"room_id": room_id, "user_email": user_email, "start_time": start_dt, "end_time": end_dt}).execute()
                    # Запись в аудит (ДЛЯ ПУНКТА 3.2)
                    supabase.table("audit_logs").insert({"user_email": user_email, "action": f"Бронь: {selected_room} на {date}"}).execute()
                    st.success("🎉 Успешно забронировано!")

    elif choice == "📅 Мои бронирования":
        st.subheader("Ваша история записей")
        res = supabase.table("bookings").select("*, rooms(name)").eq("user_email", user_email).execute()
        if res.data:
            df_my = pd.DataFrame(res.data)
            # Упростим таблицу для показа
            df_display = pd.DataFrame([{
                'Комната': b['rooms']['name'],
                'Начало': b['start_time'],
                'Конец': b['end_time']
            } for b in res.data])
            st.table(df_display)
        else:
            st.write("У вас пока нет записей.")

    elif choice == "🛡️ Журнал аудита":
        st.subheader("Журнал безопасности и событий")
        st.write("Каждое действие пользователя фиксируется в неизменяемом логе.")
        
        logs = supabase.table("audit_logs").select("*").order("created_at", desc=True).execute()
        if logs.data:
            df_logs = pd.DataFrame(logs.data)
            st.dataframe(df_logs, use_container_width=True)
            
            # ЭКСПОРТ (ДЛЯ ПУНКТА 3.2)
            csv = df_logs.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Скачать отчет аудита (CSV)",
                data=csv,
                file_name=f"audit_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
else:
    # Заглушка для неавторизованных
    st.warning("👈 Пожалуйста, войдите в систему, используя Email и пароль.")
    st.info("""
    ### Требования безопасности:
    1. Идентификация по адресу электронной почты.
    2. Парольная защита (не менее 6 знаков).
    3. Шифрование соединения с базой данных (SSL).
    """)
