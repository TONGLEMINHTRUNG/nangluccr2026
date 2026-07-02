import streamlit as st
import pandas as pd
import random
import requests
import threading

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ Thống Ôn Tập Năng Lực", page_icon="✈️", layout="wide")

# LINK GOOGLE APPS SCRIPT
API_URL = "https://script.google.com/macros/s/AKfycbyZANZPy6zjVpaLcvUsn-fYPntNlHLsTVVZUD7nd5mAKkRp9kfV4DantgZ0PpKjRHCp/exec"

# --- 2. KHAI BÁO LINK DỮ LIỆU CÂU HỎI TSV ---
SHEET_URLS = {
    "Bài thi LTC-ADC": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=1545601122&single=true&output=tsv",
    "Bài thi LTC-APP": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=272921330&single=true&output=tsv",
    "Bài thi LTCS-CR": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=0&single=true&output=tsv"
}

# --- 3. QUẢN LÝ TRẠNG THÁI (SESSION STATE) ---
def init_states():
    if 'user_name' not in st.session_state: st.session_state.user_name = ""
    if 'prev_sheet' not in st.session_state: st.session_state.prev_sheet = ""
    if 'prev_mode' not in st.session_state: st.session_state.prev_mode = ""
    if 'db_loaded' not in st.session_state: st.session_state.db_loaded = False
    if 'sync_error' not in st.session_state: st.session_state.sync_error = False
    
    if 'fc_queue' not in st.session_state: st.session_state.fc_queue = []
    if 'fc_current' not in st.session_state: st.session_state.fc_current = 0
    if 'fc_score' not in st.session_state: st.session_state.fc_score = 0
    if 'fc_answered' not in st.session_state: st.session_state.fc_answered = False
    if 'fc_choice' not in st.session_state: st.session_state.fc_choice = None
    if 'fc_incorrect' not in st.session_state: st.session_state.fc_incorrect = []
    if 'fc_is_retry' not in st.session_state: st.session_state.fc_is_retry = False

    if 'mt_indices' not in st.session_state: st.session_state.mt_indices = []
    if 'mt_submitted' not in st.session_state: st.session_state.mt_submitted = False
    if 'mt_answers' not in st.session_state: st.session_state.mt_answers = {}

init_states()

# --- CÁC HÀM TỰ ĐỘNG ĐỒNG BỘ CLOUD ---
def fetch_progress_from_db(user, quiz):
    if not API_URL or "DÁN_LINK" in API_URL: 
        st.session_state.sync_error = True
        return None
    try:
        response = requests.get(f"{API_URL}?user={user}&quiz={quiz}", timeout=5)
        if response.status_code == 200:
            st.session_state.sync_error = False
            return response.json()
    except:
        st.session_state.sync_error = True
    return None

def background_save(payload):
    """Hàm chạy ngầm gửi dữ liệu lên Google Sheets để không làm lag app"""
    try:
        requests.post(API_URL, json=payload, timeout=5)
    except:
        pass

def save_progress_to_db():
    if not API_URL or "DÁN_LINK" in API_URL or st.session_state.user_name == "" or st.session_state.fc_is_retry: 
        return
    try:
        err_str = ",".join(map(str, st.session_state.fc_incorrect))
        
        saved_current_q = st.session_state.fc_current + 1 if st.session_state.fc_answered else st.session_state.fc_current
        
        payload = {
            "user": st.session_state.user_name,
            "quiz": st.session_state.prev_sheet,
            "currentQ": saved_current_q,
            "score": st.session_state.fc_score,
            "incorrect": err_str
        }
        # Kích hoạt tiểu trình (thread) chạy ngầm để lưu dữ liệu
        threading.Thread(target=background_save, args=(payload,)).start()
    except:
        pass # Không làm phiền người dùng nếu lỗi ngầm

def reset_flashcard(df):
    st.session_state.fc_queue = list(range(len(df)))
    st.session_state.fc_current = 0
    st.session_state.fc_score = 0
    st.session_state.fc_answered = False
    st.session_state.fc_choice = None
    st.session_state.fc_incorrect = []
    st.session_state.fc_is_retry = False
    save_progress_to_db()

def retry_wrong_flashcards():
    st.session_state.fc_queue = st.session_state.fc_incorrect.copy()
    st.session_state.fc_current = 0
    st.session_state.fc_score = 0
    st.session_state.fc_answered = False
    st.session_state.fc_choice = None
    st.session_state.fc_incorrect = []
    st.session_state.fc_is_retry = True

# --- THUẬT TOÁN TẠO ĐỀ THI 50 CÂU PHÂN BỔ ĐỀU ---
def reset_mock_test(df):
    total_q = len(df)
    
    if total_q < 50:
        indices = list(range(total_q))
        random.shuffle(indices)
        st.session_state.mt_indices = indices
    else:
        indices = []
        num_parts = 10
        q_per_part = 5
        part_size = total_q // num_parts
        
        for i in range(num_parts):
            start_idx = i * part_size
            end_idx = total_q if i == num_parts - 1 else (i + 1) * part_size
            part_indices = list(range(start_idx, end_idx))
            k = min(q_per_part, len(part_indices)) 
            sampled = random.sample(part_indices, k)
            indices.extend(sampled)
            
        random.shuffle(indices)
        st.session_state.mt_indices = indices
        
    st.session_state.mt_submitted = False
    st.session_state.mt_answers = {}

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
    options_to_display = []
    
    correct_idx_str = str(row.get('Đáp án (*)', '')).strip()
    if correct_idx_str.endswith('.0'):
        correct_idx_str = correct_idx_str[:-2]
    
    correct_full_text = ""
    for i, col in enumerate(option_cols):
        if col in df_columns:
            val = str(row.get(col, '')).strip()
            if val != '' and val.lower() != 'nan':
                choice_text = f"{labels[i]}. {val}"
                options_to_display.append(choice_text)
                if str(i + 1) == correct_idx_str:
                    correct_full_text = choice_text
                    
    if correct_full_text == "":
        correct_full_text = f"Đáp án số {correct_idx_str} (Dữ liệu bị thiếu)"
    return options_to_display, correct_full_text


# --- 5. MÀN HÌNH KHAI BÁO TÊN BAN ĐẦU ---
if st.session_state.user_name == "":
    st.title("✈️ Hệ Thống Ôn Tập Năng Lực Trắc Nghiệm")
    st.subheader("Hệ thống tự động đồng bộ đám mây")
    
    st.info("💡 **Nếu bạn thấy phần mềm hữu ích nhớ mời CB uống ROOT ROOT nhé! 🍺**")
    
    with st.form("identity_form"):
        name_input = st.text_input("Nhập Tên hoặc Ký hiệu viết tắt của bạn để lưu tiến độ:")
        submit_identity = st.form_submit_button("Vào ôn luyện 🚀")
        if submit_identity:
            if name_input.strip() == "":
                st.warning("Vui lòng điền tên định danh cá nhân!")
            else:
                st.session_state.user_name = name_input.strip()
                st.session_state.db_loaded = False 
                st.rerun()
    st.stop()

# --- 6. GIAO DIỆN MENU CÀI ĐẶT BÊN CẠNH ---
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
        ["1. Flashcard (Học tự động lưu)", "2. Thi thử (50 câu ngẫu nhiên)"]
    )
    
    df = load_data(SHEET_URLS[selected_sheet], selected_sheet)
    
    if selected_sheet != st.session_state.prev_sheet or mode != st.session_state.prev_mode:
        st.session_state.prev_sheet = selected_sheet
        st.session_state.prev_mode = mode
        st.session_state.db_loaded = False 
        if not df.empty:
            reset_mock_test(df)

    # --- TIẾN HÀNH ĐỒNG BỘ DỮ LIỆU TỪ CLOUD CHO FLASHCARD ---
    if mode.startswith("1") and not df.empty and not st.session_state.db_loaded:
        with st.spinner("🔄 Đang đồng bộ tiến độ từ Google Sheets..."):
            st.session_state.fc_queue = list(range(len(df)))
            progress = fetch_progress_from_db(st.session_state.user_name, selected_sheet)
            
            if progress and progress.get("status") == "found":
                st.session_state.fc_current = min(int(progress.get("currentQ", 0)), len(df) - 1)
                st.session_state.fc_score = int(progress.get("score", 0))
                inc_str = progress.get("incorrect", "")
                st.session_state.fc_incorrect = [int(x) for x in inc_str.split(",") if x]
            else:
                st.session_state.fc_current = 0
                st.session_state.fc_score = 0
                st.session_state.fc_incorrect = []
                
            st.session_state.db_loaded = True
            st.rerun()
            
    st.divider()
    if st.button("🗑️ Xóa toàn bộ tiến độ - Làm lại đầu"):
        reset_flashcard(df)
        reset_mock_test(df)
        st.rerun()

# --- 7. KHU VỰC HIỂN THỊ CHÍNH ---
st.title("✈️ Hệ Thống Ôn Tập Trắc Nghiệm")

if st.session_state.sync_error:
    st.error("⚠️ Lỗi kết nối Đồng bộ: Không thể lưu tiến độ lúc này.")

if df.empty:
    st.warning("Sheet này hiện chưa có câu hỏi nào hợp lệ. Bạn hãy kiểm tra lại file trang tính nhé!")
else:
    # ==========================================
    # HÌNH THỨC 1: FLASHCARD (CLOUD AUTOMATED)
    # ==========================================
    if mode.startswith("1"):
        st.caption(f"Học viên: **{st.session_state.user_name}** | Tiến độ của bạn được lưu tự động lên Google Sheets")
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
            if not st.session_state.fc_is_retry:
                with st.expander("⏩ Chuyển nhanh đến câu khác", expanded=False):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        jump_to = st.number_input("Nhập số câu muốn nhảy tới:", min_value=1, max_value=queue_len, value=st.session_state.fc_current + 1, step=1)
                    with col2:
                        st.write("") 
                        st.write("")
                        if st.button("Đi tiếp 🚀"):
                            st.session_state.fc_current = jump_to - 1
                            st.session_state.fc_answered = False
                            st.session_state.fc_choice = None
                            save_progress_to_db()
                            st.rerun()
                            
            real_idx = st.session_state.fc_queue[st.session_state.fc_current]
            row = df.iloc[real_idx]
            
            st.progress(st.session_state.fc_current / queue_len)
            st.write(f"📝 **Câu {st.session_state.fc_current + 1}/{queue_len}** | 🎯 Đã đúng: **{st.session_state.fc_score}**")
            st.divider()
            
            st.markdown(f"### {row.get('Nội dung câu hỏi (*)', 'Lỗi nội dung')}")
            options, correct_ans = get_options_and_correct(row, df.columns)
            
            user_choice = st.radio(
                "Lựa chọn của bạn:", 
                options, 
                key=f"fc_radio_{real_idx}",
                index=None,
                disabled=st.session_state.fc_answered
            )
            
            st.write("---")
            
            if not st.session_state.fc_answered:
                if st.button("Kiểm tra kết quả 🔍"):
                    if user_choice is None:
                        st.warning("Vui lòng chọn một đáp án!")
                    else:
                        st.session_state.fc_choice = user_choice
                        st.session_state.fc_answered = True
                        if user_choice == correct_ans:
                            st.session_state.fc_score += 1
                        else:
                            if real_idx not in st.session_state.fc_incorrect:
                                st.session_state.fc_incorrect.append(real_idx)
                        save_progress_to_db()
                        st.rerun()
            else:
                if st.session_state.fc_choice == correct_ans:
                    st.success(f"✅ **Chính xác!** {correct_ans}")
                else:
                    st.error(f"❌ **Sai rồi!** Bạn chọn: {st.session_state.fc_choice}")
                    st.info(f"💡 **Đáp án đúng là:** {correct_ans}")
                
                if st.button("Câu tiếp theo ➡️"):
                    st.session_state.fc_current += 1
                    st.session_state.fc_answered = False
                    st.session_state.fc_choice = None
                    save_progress_to_db()
                    st.rerun()

    # ==========================================
    # HÌNH THỨC 2: THI THỬ 50 CÂU
    # ==========================================
    elif mode.startswith("2"):
        st.caption(f"Học viên: **{st.session_state.user_name}** | Chế độ: Thi thử 50 câu (Phân bổ đều)")
        
        if not st.session_state.mt_submitted:
            with st.form("mock_test_form"):
                current_answers = {}
                for i, idx in enumerate(st.session_state.mt_indices):
                    row = df.iloc[idx]
                    st.markdown(f"**Câu {i + 1}: {row.get('Nội dung câu hỏi (*)', '')}**")
                    options, _ = get_options_and_correct(row, df.columns)
                    
                    current_answers[idx] = st.radio(
                        "Chọn đáp án:", 
                        options, 
                        key=f"mt_q_{idx}",
                        index=None
                    )
                    st.write("---")
                
                if st.form_submit_button("Nộp bài & Chấm điểm ✅"):
                    st.session_state.mt_answers = current_answers
                    st.session_state.mt_submitted = True
                    st.rerun()
                    
        else:
            score = 0
            results_ui = []
            
            for i, idx in enumerate(st.session_state.mt_indices):
                row = df.iloc[idx]
                options, correct_ans = get_options_and_correct(row, df.columns)
                user_ans = st.session_state.mt_answers.get(idx)
                
                ui_block = f"**Câu {i + 1}: {row.get('Nội dung câu hỏi (*)', '')}**\n\n"
                if user_ans == correct_ans:
                    score += 1
                    ui_block += f"✅ **Chính xác:** {correct_ans}"
                elif user_ans is None:
                    ui_block += f"⚠️ **Chưa trả lời** (Đáp án đúng: {correct_ans})"
                else:
                    ui_block += f"❌ **Sai.** Bạn chọn: {user_ans}  \n💡 **Đáp án đúng:** {correct_ans}"
                
                results_ui.append(ui_block)

            st.success(f"### 🏆 Điểm số của {st.session_state.user_name}: {score} / {len(st.session_state.mt_indices)}")
            st.divider()
            
            for block in results_ui:
                st.markdown(block)
                st.write("---")
                
            if score == len(st.session_state.mt_indices):
                st.balloons()
