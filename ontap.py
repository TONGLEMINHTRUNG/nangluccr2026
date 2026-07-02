import streamlit as st
import pandas as pd
import random
import requests
import json
from concurrent.futures import ThreadPoolExecutor

# --- 1. CẤU HÌNH GIAO DIỆN VÀ CSS THU GỌN ---
st.set_page_config(page_title="Phần mềm ôn thi Cam Ranh", page_icon="✈️", layout="wide")

st.markdown("""
    <style>
    /* 1. TÙY CHỈNH KHU VỰC LÀM BÀI CHÍNH (MAIN) */
    section[data-testid="stMain"] div[role="radiogroup"] label p {
        font-size: 17px !important;
        font-weight: 500;
    }
    section[data-testid="stMain"] .stMarkdown, section[data-testid="stMain"] .stRadio {
        margin-bottom: -10px !important;
    }
    section[data-testid="stMain"] div[data-testid="stMarkdownContainer"] {
        margin-bottom: 5px !important;
    }

    /* 2. TÙY CHỈNH KHU VỰC MENU TRÁI (SIDEBAR) ĐỂ SIÊU GỌN GÀNG */
    section[data-testid="stSidebar"] div[role="radiogroup"] label p {
        font-size: 14px !important;
    }
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] div[data-baseweb="select"] {
        font-size: 14px !important;
    }
    section[data-testid="stSidebar"] h1 {
        font-size: 20px !important;
        padding-bottom: 0px !important;
    }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
        font-size: 16px !important;
        padding-bottom: 0px !important;
        margin-bottom: -10px !important;
    }

    /* 3. THU GỌN ĐƯỜNG KẺ CHUNG */
    hr {
        margin-top: 10px !important;
        margin-bottom: 10px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Lấy đường link API bảo mật từ Streamlit Secrets
API_URL = st.secrets.get("API_URL", "")

# Khởi tạo ThreadPoolExecutor để đẩy dữ liệu chạy ngầm dưới nền, không block UI
if 'executor' not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=2)

# --- 2. KHAI BÁO LINK DỮ LIỆU ---
SHEET_URLS = {
    "Bài thi LTC-ADC": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=1545601122&single=true&output=tsv",
    "Bài thi LTC-APP": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=272921330&single=true&output=tsv",
    "Bài thi LTCS-CR": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=0&single=true&output=tsv"
}

# --- 3. QUẢN LÝ TRẠNG THÁI ---
def init_states():
    if 'user_name' not in st.session_state: st.session_state.user_name = ""
    if 'prev_sheet' not in st.session_state: st.session_state.prev_sheet = ""
    if 'prev_mode' not in st.session_state: st.session_state.prev_mode = ""
    if 'db_loaded' not in st.session_state: st.session_state.db_loaded = False
    
    # Flashcard State (Đã làm sạch, loại bỏ các biến thừa)
    if 'fc_queue' not in st.session_state: st.session_state.fc_queue = []
    if 'fc_current' not in st.session_state: st.session_state.fc_current = 0
    if 'fc_score' not in st.session_state: st.session_state.fc_score = 0
    if 'fc_incorrect' not in st.session_state: st.session_state.fc_incorrect = []
    if 'fc_is_retry' not in st.session_state: st.session_state.fc_is_retry = False
    if 'fc_history_choices' not in st.session_state: st.session_state.fc_history_choices = {} # Bộ nhớ lưu lịch sử đáp án đã chọn

    # Mock Test State
    if 'mt_indices' not in st.session_state: st.session_state.mt_indices = []
    if 'mt_submitted' not in st.session_state: st.session_state.mt_submitted = False
    if 'mt_answers' not in st.session_state: st.session_state.mt_answers = {}

init_states()

# --- CÁC HÀM TỰ ĐỘNG ĐỒNG BỘ CLOUD (BẤT ĐỒNG BỘ - SIÊU TỐC) ---
def fetch_progress_from_db(user, quiz):
    if not API_URL: return None
    try:
        res = requests.get(f"{API_URL}?action=get_progress&user={user}&quiz={quiz}", timeout=5)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def fetch_history_from_db(user):
    if not API_URL: return []
    try:
        res = requests.get(f"{API_URL}?action=get_history&user={user}", timeout=5)
        if res.status_code == 200: return res.json()
    except: pass
    return []

def _async_post_request(url, payload):
    try:
        requests.post(url, json=payload, timeout=5)
    except: pass

def save_fc_progress():
    if not API_URL or st.session_state.user_name == "" or st.session_state.fc_is_retry: return
    err_str = ",".join(map(str, st.session_state.fc_incorrect))
    payload = {
        "action": "save_progress", "mode": "flashcard",
        "user": st.session_state.user_name, "quiz": st.session_state.prev_sheet,
        "currentQ": st.session_state.fc_current, "score": st.session_state.fc_score, "incorrect": err_str
    }
    st.session_state.executor.submit(_async_post_request, API_URL, payload)

def save_mt_progress():
    if not API_URL or st.session_state.user_name == "" or st.session_state.mt_submitted: return
    payload = {
        "action": "save_progress", "mode": "mocktest",
        "user": st.session_state.user_name, "quiz": st.session_state.prev_sheet,
        "mt_indices": json.dumps(st.session_state.mt_indices),
        "mt_answers": json.dumps(st.session_state.mt_answers),
        "mt_submitted": st.session_state.mt_submitted
    }
    st.session_state.executor.submit(_async_post_request, API_URL, payload)

def save_mt_history(score, total):
    if not API_URL or st.session_state.user_name == "": return
    payload = {
        "action": "save_history",
        "user": st.session_state.user_name, "quiz": st.session_state.prev_sheet,
        "score": score, "total": total
    }
    st.session_state.executor.submit(_async_post_request, API_URL, payload)

def on_mt_answer_change(idx_str):
    selected_val = st.session_state[f"mt_radio_{idx_str}"]
    st.session_state.mt_answers[idx_str] = selected_val
    save_mt_progress()

def reset_flashcard(df):
    st.session_state.fc_queue = list(range(len(df)))
    st.session_state.fc_current = 0
    st.session_state.fc_score = 0
    st.session_state.fc_incorrect = []
    st.session_state.fc_is_retry = False
    st.session_state.fc_history_choices = {}
    save_fc_progress()

def retry_wrong_flashcards():
    st.session_state.fc_queue = st.session_state.fc_incorrect.copy()
    st.session_state.fc_current = 0
    st.session_state.fc_score = 0
    st.session_state.fc_incorrect = []
    st.session_state.fc_is_retry = True
    st.session_state.fc_history_choices = {} # Làm mới lịch sử cho vòng lặp ôn lại

def reset_mock_test(df):
    k = min(50, len(df))
    st.session_state.mt_indices = random.sample(list(range(len(df))), k)
    st.session_state.mt_submitted = False
    st.session_state.mt_answers = {}
    save_mt_progress()

# --- 4. TẢI DỮ LIỆU ĐỀ THI ---
@st.cache_data(ttl=600) 
def load_data(url, sheet_name):
    df_raw = pd.read_csv(url, sep='\t', header=None, dtype=str)
    header_row_idx = 0
    for i, row in df_raw.iterrows():
        if any(isinstance(val, str) and "nội dung câu hỏi" in val.lower() for val in row.values):
            header_row_idx = i
            break
            
    df_raw.columns = df_raw.iloc[header_row_idx]
    df = df_raw.iloc[header_row_idx + 1:].copy()
    df.reset_index(drop=True, inplace=True)
    df.columns = [str(col).strip() for col in df.columns]
    
    if 'Nội dung câu hỏi (*)' in df.columns:
        df = df.dropna(subset=['Nội dung câu hỏi (*)'])
        df = df[df['Nội dung câu hỏi (*)'].str.strip() != '']
    return df

def get_options_and_correct(row, df_columns):
    labels = ['A', 'B', 'C', 'D']
    option_cols = ['Phương án lựa chọn 1', 'Phương án lựa chọn 2', 'Phương án lựa chọn 3', 'Phương án lựa chọn 4']
    options = []
    
    correct_idx_str = str(row.get('Đáp án (*)', '')).strip()
    if correct_idx_str.endswith('.0'): correct_idx_str = correct_idx_str[:-2]
    
    correct_full_text = ""
    for i, col in enumerate(option_cols):
        if col in df_columns:
            val = str(row.get(col, '')).strip()
            if val != '' and val.lower() != 'nan':
                choice_text = f"{labels[i]}. {val}"
                options.append(choice_text)
                if str(i + 1) == correct_idx_str:
                    correct_full_text = choice_text
                    
    if correct_full_text == "": correct_full_text = f"Đáp án số {correct_idx_str} (Bị thiếu)"
    return options, correct_full_text

# --- 5. MÀN HÌNH KHAI BÁO TÊN BAN ĐẦU ---
if st.session_state.user_name == "":
    st.title("✈️ Phần mềm ôn thi Cam Ranh")
    st.subheader("Hệ thống tự động đồng bộ đám mây")
    
    with st.form("identity_form"):
        name_input = st.text_input("Nhập Tên hoặc Initial Name của bạn để lưu tiến độ:")
        submit_identity = st.form_submit_button("Login 🚀")
        if submit_identity:
            if name_input.strip() == "":
                st.warning("Vui lòng điền tên định danh cá nhân!")
            else:
                st.session_state.user_name = name_input.strip()
                st.session_state.db_loaded = False
                st.rerun()
    
    st.markdown("<br><hr><p style='text-align: center; color: gray; font-style: italic;'>💡 Nếu thấy hữu ích nhớ mời CB uống ROOT ROOT 🍺</p>", unsafe_allow_html=True)
    st.stop()

# --- 6. GIAO DIỆN MENU CÀI ĐẶT ---
with st.sidebar:
    st.success(f"👤 Học viên: **{st.session_state.user_name}**")
    if st.button("🚪 Đổi tài khoản / Đăng xuất"):
        st.session_state.user_name = ""
        st.session_state.db_loaded = False
        st.rerun()
        
    st.divider()
    st.title("⚙️ Cài đặt")
    selected_sheet = st.selectbox("📌 Chọn bài thi:", list(SHEET_URLS.keys()))
    mode = st.radio(
        "📖 Chọn hình thức học:", 
        ["1. Flashcard ", "2. Thi thử (50 câu ngẫu nhiên)", "3. 🏆 Xem Lịch Sử Thi"]
    )
    
    df = load_data(SHEET_URLS[selected_sheet], selected_sheet)
    
    if selected_sheet != st.session_state.prev_sheet or mode != st.session_state.prev_mode:
        st.session_state.prev_sheet = selected_sheet
        st.session_state.prev_mode = mode
        st.session_state.db_loaded = False 

    # --- TẢI TIẾN ĐỘ TỪ CLOUD ---
    if not mode.startswith("3") and not df.empty and not st.session_state.db_loaded:
        with st.spinner("🔄 Đang đồng bộ tiến độ từ Cloud..."):
            st.session_state.fc_queue = list(range(len(df)))
            progress = fetch_progress_from_db(st.session_state.user_name, selected_sheet)
            
            if progress and progress.get("status") == "found":
                st.session_state.fc_current = min(int(progress.get("fc_currentQ", 0)), len(df) - 1)
                st.session_state.fc_score = int(progress.get("fc_score", 0))
                inc_str = progress.get("fc_incorrect", "")
                st.session_state.fc_incorrect = [int(x) for x in inc_str.split(",") if x]
                
                mt_idx_str = progress.get("mt_indices", "")
                mt_ans_str = progress.get("mt_answers", "{}")
                mt_sub_str = str(progress.get("mt_submitted", "False"))
                
                if mt_idx_str:
                    st.session_state.mt_indices = json.loads(mt_idx_str)
                    st.session_state.mt_answers = json.loads(mt_ans_str)
                    st.session_state.mt_submitted = True if mt_sub_str.lower() == "true" else False
                else:
                    reset_mock_test(df)
            else:
                st.session_state.fc_current = 0
                st.session_state.fc_score = 0
                st.session_state.fc_incorrect = []
                reset_mock_test(df)
                
            st.session_state.db_loaded = True
            st.rerun()
            
    st.divider()
    if not mode.startswith("3"):
        if st.button("🗑️ Reset profile"):
            if mode.startswith("1"): reset_flashcard(df)
            else: reset_mock_test(df)
            st.rerun()
            
    st.write("---")
    st.markdown("<p style='text-align: center; color: #888; font-style: italic; font-size: 14px;'>💡 Nếu thấy hữu ích nhớ mời CB uống ROOT ROOT 🍺</p>", unsafe_allow_html=True)

# --- 7. KHU VỰC HIỂN THỊ CHÍNH ---
st.title("✈️ Hệ Thống Ôn Tập Trắc Nghiệm")

if mode.startswith("3"):
    st.header("🏆 Lịch Sử Các Bài Đã Thi")
    with st.spinner("Đang tải dữ liệu lịch sử..."):
        history_data = fetch_history_from_db(st.session_state.user_name)
        
    if not history_data:
        st.info("Bạn chưa có lịch sử làm bài thi thử nào trên hệ thống.")
    else:
        for idx, record in enumerate(history_data):
            score = int(record['score'])
            total = int(record['total'])
            pass_rate = (score / total) * 100
            
            with st.container():
                col1, col2, col3 = st.columns([1, 2, 1])
                col1.write(f"🕒 **{record['time']}**")
                col2.write(f"📘 {record['quiz']}")
                if pass_rate >= 80:
                    col3.success(f"Điểm: **{score}/{total}** ({pass_rate:.0f}%) - ĐẠT")
                else:
                    col3.error(f"Điểm: **{score}/{total}** ({pass_rate:.0f}%) - TRƯỢT")
                st.divider()
                
elif df.empty:
    st.warning("Sheet này hiện chưa có câu hỏi nào hợp lệ. Bạn hãy kiểm tra lại file trang tính nhé!")
else:
    # ==========================================
    # HÌNH THỨC 1: FLASHCARD
    # ==========================================
    if mode.startswith("1"):
        st.caption(f"Học viên: **{st.session_state.user_name}** | Tiến độ của bạn được lưu tự động")
        queue_len = len(st.session_state.fc_queue)
        
        num_incorrect = len(st.session_state.fc_incorrect)
        if num_incorrect > 0:
            with st.expander(f"👀 Xem danh sách {num_incorrect} câu bạn đã làm sai", expanded=False):
                for err_idx in st.session_state.fc_incorrect:
                    if err_idx < len(df):
                        err_row = df.iloc[err_idx]
                        _, corr_ans = get_options_and_correct(err_row, df.columns)
                        st.markdown(f"**Câu {err_idx + 1}:** {err_row.get('Nội dung câu hỏi (*)', '')}")
                        st.markdown(f"✅ *Đáp án đúng:* {corr_ans}")
                        st.write("---")
        
        if queue_len == 0:
            st.info("Chưa có dữ liệu câu hỏi.")
        elif st.session_state.fc_current >= queue_len:
            st.success("🎉 Bạn đã hoàn thành chuỗi câu hỏi này!")
            st.write(f"### 🎯 Kết quả tổng kết: {st.session_state.fc_score} / {queue_len}")
            
            if num_incorrect > 0:
                st.warning(f"⚠️ Bạn còn {num_incorrect} câu làm sai cần giải quyết.")
                if st.button("🔄 Luyện tập lại các câu làm sai"):
                    retry_wrong_flashcards()
                    st.rerun()
        else:
            if st.session_state.fc_current not in st.session_state.fc_history_choices:
                with st.expander("⏩ Chuyển nhanh đến câu khác", expanded=False):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        jump_to = st.number_input("Nhập số câu muốn nhảy tới:", min_value=1, max_value=queue_len, value=st.session_state.fc_current + 1, step=1)
                    with col2:
                        st.write("") 
                        st.write("")
                        if st.button("Đi tiếp 🚀"):
                            st.session_state.fc_current = jump_to - 1
                            save_fc_progress()
                            st.rerun()
                            
            real_idx = st.session_state.fc_queue[st.session_state.fc_current]
            row = df.iloc[real_idx]
            
            st.progress(st.session_state.fc_current / queue_len)
            
            # --- CẬP NHẬT LOGIC TÍNH TOÁN "ĐÃ LÀM" = ĐÚNG + SAI ---
            so_cau_dung = st.session_state.fc_score
            so_cau_sai = len(st.session_state.fc_incorrect)
            so_cau_da_lam = so_cau_dung + so_cau_sai
            
            status_text = f"📝 **Câu {st.session_state.fc_current + 1}/{queue_len}**"
            if st.session_state.fc_is_retry:
                status_text += " *(Luyện câu sai)*"
            status_text += f" &nbsp;|&nbsp; 🏁 Đã làm: **{so_cau_da_lam}** &nbsp;|&nbsp; ✅ Đúng: **{so_cau_dung}** &nbsp;|&nbsp; ❌ Sai: **{so_cau_sai}**"
            
            st.write(status_text)
            st.divider()
            
            st.markdown(f"### {row.get('Nội dung câu hỏi (*)', 'Lỗi nội dung')}")
            options, correct_ans = get_options_and_correct(row, df.columns)
            
            # KIỂM TRA LỊCH SỬ ĐÁP ÁN ĐỂ CHỐT CHẶN (NÚT BACK ĐƯỢC GIẢI QUYẾT TẠI ĐÂY)
            is_answered = real_idx in st.session_state.fc_history_choices
            current_index = None

            if is_answered:
                saved_choice = st.session_state.fc_history_choices[real_idx]
                if saved_choice in options:
                    current_index = options.index(saved_choice)

            user_choice = st.radio(
                "Lựa chọn của bạn:", 
                options, 
                key=f"fc_radio_{real_idx}",
                index=current_index,
                disabled=is_answered # Khóa cứng nếu đã trả lời
            )
            
            st.write("---")
            
            # --- KHU VỰC NÚT ĐIỀU HƯỚNG ---
            col_b1, col_b2, col_b3 = st.columns([1, 1, 4])
            
            if st.session_state.fc_current > 0:
                if col_b1.button("⬅️ Back"):
                    st.session_state.fc_current -= 1
                    st.rerun()
            
            if not is_answered:
                if col_b2.button("🔍 Đáp án"):
                    if user_choice is None:
                        st.warning("Vui lòng chọn một đáp án!")
                    else:
                        # CHẤM ĐIỂM VÀ LƯU LỊCH SỬ DUY NHẤT 1 LẦN DÙ BACK TỚI LUI
                        st.session_state.fc_history_choices[real_idx] = user_choice
                        
                        if user_choice == correct_ans:
                            st.session_state.fc_score += 1
                        else:
                            if real_idx not in st.session_state.fc_incorrect:
                                st.session_state.fc_incorrect.append(real_idx)
                        
                        save_fc_progress()
                        st.rerun()
            else:
                if col_b2.button("Next ➡️"):
                    st.session_state.fc_current += 1
                    save_fc_progress()
                    st.rerun()
                    
            # HIỂN THỊ KẾT QUẢ ĐÚNG/SAI NGAY LẬP TỨC CHO DÙ LÀ CÂU MỚI KIỂM TRA HAY CÂU CŨ BACK LẠI
            if is_answered:
                active_choice = st.session_state.fc_history_choices[real_idx]
                if active_choice == correct_ans:
                    st.success(f"✅ **Chính xác!** {correct_ans}")
                else:
                    st.error(f"❌ **Sai rồi!** Bạn chọn: {active_choice}")
                    st.info(f"💡 **Đáp án đúng là:** {correct_ans}")

    # ==========================================
    # HÌNH THỨC 2: THI THỬ 50 CÂU (LƯU VỊ TRÍ)
    # ==========================================
    elif mode.startswith("2"):
        st.caption(f"Học viên: **{st.session_state.user_name}** | Chế độ: Thi thử (Hệ thống tự lưu đáp án khi bạn chọn)")
        
        if not st.session_state.mt_submitted:
            answered_count = len([x for x in st.session_state.mt_answers.values() if x is not None])
            st.progress(answered_count / len(st.session_state.mt_indices))
            st.write(f"✅ Đã làm: **{answered_count} / {len(st.session_state.mt_indices)}** câu")
            
            for i, idx in enumerate(st.session_state.mt_indices):
                idx_str = str(idx)
                row = df.iloc[idx]
                st.markdown(f"**Câu {i + 1}: {row.get('Nội dung câu hỏi (*)', '')}**")
                
                options, _ = get_options_and_correct(row, df.columns)
                prev_val = st.session_state.mt_answers.get(idx_str)
                default_idx = options.index(prev_val) if prev_val in options else None
                
                st.radio(
                    "Chọn đáp án:", 
                    options, 
                    key=f"mt_radio_{idx_str}",
                    index=default_idx,
                    on_change=on_mt_answer_change,
                    args=(idx_str,)
                )
                st.write("---")
            
            st.warning("⚠️ Nhớ kiểm tra kỹ đáp án trước khi bấm Nộp bài nhé!")
            if st.button("NỘP BÀI & CHẤM ĐIỂM ✅"):
                st.session_state.mt_submitted = True
                save_mt_progress()
                st.rerun()
                
        else:
            score = 0
            results_ui = []
            
            for i, idx in enumerate(st.session_state.mt_indices):
                idx_str = str(idx)
                row = df.iloc[idx]
                options, correct_ans = get_options_and_correct(row, df.columns)
                user_ans = st.session_state.mt_answers.get(idx_str)
                
                ui_block = f"**Câu {i + 1}: {row.get('Nội dung câu hỏi (*)', '')}**\n\n"
                if user_ans == correct_ans:
                    score += 1
                    ui_block += f"✅ **Chính xác:** {correct_ans}"
                elif user_ans is None:
                    ui_block += f"⚠️ **Chưa trả lời** (Đáp án đúng: {correct_ans})"
                else:
                    ui_block += f"❌ **Sai.** Bạn chọn: {user_ans}  \n💡 **Đáp án đúng:** {correct_ans}")
                
                results_ui.append(ui_block)

            save_mt_history(score, len(st.session_state.mt_indices))

            st.success(f"### 🏆 Điểm số của {st.session_state.user_name}: {score} / {len(st.session_state.mt_indices)}")
            st.divider()
            
            for block in results_ui:
                st.markdown(block)
                st.write("---")
