import streamlit as st
import pandas as pd
import random

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ Thống Ôn Tập Năng Lực", page_icon="✈️", layout="wide")

# --- 2. KHAI BÁO LINK DỮ LIỆU TSV ---
SHEET_URLS = {
    "Bài thi LTCS-CR": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=1545601122&single=true&output=tsv",
    "Bài thi LTC-APP": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=272921330&single=true&output=tsv",
    "Bài thi LTC-ADC": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6N9VuIhj0OxwG6DaGbAb380C6XkRGVDyZ72pwd6FVRrzKB7Mw9m5ypdCB3TGCBgQPSz6Xpfkyiq5p/pub?gid=0&single=true&output=tsv"
}

# --- 3. QUẢN LÝ TRẠNG THÁI (SESSION STATE) ---
def init_states():
    if 'prev_sheet' not in st.session_state: st.session_state.prev_sheet = ""
    if 'prev_mode' not in st.session_state: st.session_state.prev_mode = ""
    
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

def reset_flashcard(df):
    st.session_state.fc_queue = list(range(len(df)))
    st.session_state.fc_current = 0
    st.session_state.fc_score = 0
    st.session_state.fc_answered = False
    st.session_state.fc_choice = None
    st.session_state.fc_incorrect = []
    st.session_state.fc_is_retry = False

def retry_wrong_flashcards():
    st.session_state.fc_queue = st.session_state.fc_incorrect.copy()
    st.session_state.fc_current = 0
    st.session_state.fc_score = 0
    st.session_state.fc_answered = False
    st.session_state.fc_choice = None
    st.session_state.fc_incorrect = []
    st.session_state.fc_is_retry = True

def reset_mock_test(df):
    k = min(50, len(df))
    st.session_state.mt_indices = random.sample(list(range(len(df))), k)
    st.session_state.mt_submitted = False
    st.session_state.mt_answers = {}

# --- 4. TẢI DỮ LIỆU ---
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


# --- 5. GIAO DIỆN MENU BÊN TRÁI ---
with st.sidebar:
    st.title("⚙️ Cài đặt")
    selected_sheet = st.selectbox("📌 Chọn bài thi:", list(SHEET_URLS.keys()))
    mode = st.radio(
        "📖 Chọn hình thức học:", 
        ["1. Flashcard (Từng câu & Luyện lỗi sai)", "2. Thi thử (50 câu ngẫu nhiên)"]
    )
    
    df = load_data(SHEET_URLS[selected_sheet], selected_sheet)
    
    if selected_sheet != st.session_state.prev_sheet or mode != st.session_state.prev_mode:
        if not df.empty:
            reset_flashcard(df)
            reset_mock_test(df)
        st.session_state.prev_sheet = selected_sheet
        st.session_state.prev_mode = mode
        
    st.divider()
    if st.button("🔄 Tạo mới / Làm lại từ đầu"):
        reset_flashcard(df)
        reset_mock_test(df)
        st.rerun()

# --- 6. KHU VỰC HIỂN THỊ CHÍNH ---
st.title("✈️ Hệ Thống Ôn Tập Trắc Nghiệm")

if df.empty:
    st.warning("Sheet này hiện chưa có câu hỏi nào hợp lệ. Bạn hãy kiểm tra lại file trang tính nhé!")
else:
    # ==========================================
    # HÌNH THỨC 1: FLASHCARD (CÓ TÍNH NĂNG CHỌN CÂU)
    # ==========================================
    if mode.startswith("1"):
        st.caption(f"Đang học: **{selected_sheet}** | Chế độ: Flashcard")
        queue_len = len(st.session_state.fc_queue)
        
        if queue_len == 0:
            st.info("Chưa có câu hỏi nào trong hàng chờ.")
        elif st.session_state.fc_current >= queue_len:
            st.success("🎉 Bạn đã hoàn thành chuỗi câu hỏi này!")
            st.write(f"### 🎯 Điểm số: {st.session_state.fc_score} / {queue_len}")
            
            num_incorrect = len(st.session_state.fc_incorrect)
            if num_incorrect > 0:
                st.warning(f"⚠️ Bạn có **{num_incorrect}** câu trả lời sai cần ôn lại.")
                if st.button("🔄 Bắt đầu luyện lại các câu sai"):
                    retry_wrong_flashcards()
                    st.rerun()
            else:
                st.balloons()
        else:
            # TÍNH NĂNG NHẢY CÂU (JUMP TO QUESTION)
            if not st.session_state.fc_is_retry:
                with st.expander("⏩ Chuyển nhanh đến câu khác", expanded=False):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        jump_to = st.number_input("Nhập số thứ tự câu hỏi muốn làm:", min_value=1, max_value=queue_len, value=st.session_state.fc_current + 1, step=1)
                    with col2:
                        st.write("") # Căn chỉnh nút bấm
                        st.write("")
                        if st.button("Chuyển đến 🚀"):
                            st.session_state.fc_current = jump_to - 1
                            st.session_state.fc_answered = False
                            st.session_state.fc_choice = None
                            st.rerun()
                            
            real_idx = st.session_state.fc_queue[st.session_state.fc_current]
            row = df.iloc[real_idx]
            
            progress_val = st.session_state.fc_current / queue_len
            st.progress(progress_val)
            
            status_text = f"📝 **Câu {st.session_state.fc_current + 1}/{queue_len}** "
            if st.session_state.fc_is_retry:
                status_text += " *(Chế độ luyện câu sai)*"
            status_text += f" | ✅ Đã đúng: **{st.session_state.fc_score}**"
            st.write(status_text)
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
                            st.session_state.fc_incorrect.append(real_idx)
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
                    st.rerun()

    # ==========================================
    # HÌNH THỨC 2: THI THỬ 50 CÂU
    # ==========================================
    elif mode.startswith("2"):
        st.caption(f"Đang thi thử: **{selected_sheet}** | Đề thi gồm {len(st.session_state.mt_indices)} câu ngẫu nhiên")
        
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

            st.success(f"### 🏆 Điểm của bạn: {score} / {len(st.session_state.mt_indices)}")
            st.divider()
            
            for block in results_ui:
                st.markdown(block)
                st.write("---")
                
            if score == len(st.session_state.mt_indices):
                st.balloons()
