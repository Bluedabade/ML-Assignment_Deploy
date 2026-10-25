"""Thai presentation layer shared by local and cloud; inference stays in adapters."""
import hashlib
import time
import streamlit as st
from .config import CLASSES, LIMITS, PROFILES, mode
from .errors import AppError, MESSAGES
from .media import COLORS, decode_image
from .presentation import (CUSTOM, CACHE_SLOT, display_thresholds, candidate_cache_key,
    make_image_cache, get_image_cache, build_image_result)
from .skincare_guidance import (SKINCARE_GUIDANCE, GENERAL_CARE, NUTRIENTS,
    NUTRITION_REFERENCES, MEDICAL_DISCLAIMER, NUTRITION_DISCLAIMER,
    INGREDIENT_CAUTION, NO_DETECTION_MESSAGE, guidance_topics, CONCERN_DISCLAIMER,
    CONCERN_OPTIONS, OTHER_CONCERN, selected_concerns, guidance_origins, context_intro,
    concern_session_key, clear_concerns)

PAGES = ('หน้าหลัก', 'ตรวจจับจากภาพ', 'ตรวจจับจากวิดีโอ', 'ผลการทดสอบโมเดล', 'เกี่ยวกับโครงงาน', 'คำแนะนำการใช้งาน')
THAI = dict(zip(CLASSES, ('สิว', 'ริ้วรอย', 'จุดด่างดำ', 'รูขุมขนกว้าง')))
PROFILE_LABELS = {'Balanced': 'สมดุล', 'Precision-focused': 'เน้นความแม่นยำของผลที่แสดง'}
THEME_LABELS = {'system':'ตามระบบ', 'light':'☀ สว่าง', 'dark':'☾ มืด'}
DISCLAIMER = 'ระบบนี้เป็นเครื่องมือสาธิตด้านการเรียนรู้ของเครื่อง ไม่ใช่เครื่องมือวินิจฉัยโรคหรือประเมินสุขภาพผิวทางการแพทย์'
COLUMNS = {'class_name': 'ประเภท', 'confidence': 'ความเชื่อมั่น', 'timestamp_seconds': 'เวลาในวิดีโอ (วินาที)',
           'detections': 'จำนวนตำแหน่ง', 'x1': 'พิกัดซ้าย', 'y1': 'พิกัดบน', 'x2': 'พิกัดขวา', 'y2': 'พิกัดล่าง'}
CSS = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;500;600;700&display=swap');
:root {--navy:#16324F;--teal:#0D9488;--surface:#fff;--ink:#1F2937;--muted:#536579;--line:#dce5ef;--canvas:#F5F8FC}
@media(prefers-color-scheme:dark){:root{--surface:#152638;--ink:#edf4fc;--muted:#bac9da;--line:#334b63;--canvas:#0d1927;--teal:#5eead4}}
.stApp {font-family:'Noto Sans Thai','Prompt','Tahoma',sans-serif;background:var(--canvas);color:var(--ink)}
h1,h2,h3,h4,p,li,button,label,input,select,textarea {font-family:'Noto Sans Thai','Prompt','Tahoma',sans-serif!important}
h1,h2,h3 {color:inherit}
h1{font-size:clamp(1.65rem,3vw,2.65rem)!important;line-height:1.45!important;letter-spacing:-.02em}
h2{font-size:1.5rem!important} h3{font-size:1.15rem!important}
.block-container{max-width:1280px;padding-top:2.5rem;padding-bottom:3rem}
.hero{background:linear-gradient(120deg,#16324F,#125b68);color:white;padding:2rem;border-radius:24px;margin:1rem 0}
.hero p{color:#dcebf5;max-width:760px;line-height:1.9}.eyebrow{letter-spacing:.06em;font-size:.8rem;color:#8de6db}
.hero h2{font-size:clamp(1.5rem,3vw,2.2rem)!important;color:white;line-height:1.6}
.card{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:1.35rem;min-height:180px;box-shadow:0 6px 24px #16324f08;margin-bottom:1rem}
.card p{color:var(--muted);line-height:1.8}.card small{color:var(--muted)}.badge{display:inline-block;background:#0d948820;color:var(--teal);border-radius:20px;padding:.25rem .75rem;font-size:.85rem}
.empty{text-align:center;padding:3rem 1rem;border:2px dashed var(--line);border-radius:20px;color:var(--muted);margin:1rem 0}
.legend{display:flex;flex-wrap:wrap;gap:1rem;font-size:.9rem;margin:1rem 0}.dot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:.4rem}
button{border-radius:12px!important;transition:box-shadow .15s}button:hover{box-shadow:0 3px 12px #0d948826}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #0D9488!important;outline-offset:3px}
[data-testid="stBaseButton-primary"]{background:#16324F;border-color:#16324F;color:white}
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--line);padding:1rem;border-radius:16px}
[data-testid="stSidebar"]{border-right:1px solid var(--line);background:var(--surface);color:var(--ink)}
[data-testid="stSidebar"] p,[data-testid="stRadio"] p,[data-testid="stWidgetLabel"] p{color:var(--ink)}
[data-testid="stSidebar"] a{color:var(--teal)}
[data-testid="stHeader"]{background:var(--surface);color:var(--ink)}
[data-testid="stHeader"] button,[data-testid="stSidebar"] button{color:var(--ink)}
/* Keep native Streamlit sidebar controls visible; only their appearance changes. */
[data-testid="stSidebarCollapseButton"]{opacity:1!important;visibility:visible!important}
[data-testid="stSidebarCollapseButton"] button,[data-testid="stExpandSidebarButton"]{
  min-width:88px;min-height:44px;padding:8px 12px!important;gap:6px;
  background:#0D9488!important;color:#fff!important;border:2px solid #5eead4!important;
  border-radius:12px!important;opacity:1!important;visibility:visible!important;
  box-shadow:0 3px 10px #0003;font-weight:600}
[data-testid="stSidebarCollapseButton"] button [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"]{color:#fff!important;font-size:24px}
[data-testid="stSidebarCollapseButton"] button::after{content:'ซ่อนเมนู';font-size:14px;white-space:nowrap}
[data-testid="stExpandSidebarButton"]::after{content:'เมนู';font-size:14px;white-space:nowrap}
[data-testid="stSidebarCollapseButton"] button:hover,[data-testid="stExpandSidebarButton"]:hover{background:#0f766e!important}
[data-testid="stSidebarCollapseButton"] button:focus-visible,[data-testid="stExpandSidebarButton"]:focus-visible{
  outline:3px solid #fbbf24!important;outline-offset:3px}
[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"]{background:var(--surface);color:var(--ink);border-color:var(--line)}
[data-testid="stFileUploaderDropzone"]{background:var(--surface);color:var(--ink);border:1px dashed var(--line)}
[data-testid="stFileUploaderDropzone"] small{color:var(--muted)}
[data-testid="stMetric"]{color:var(--ink)}
[data-testid="stMetricLabel"],[data-testid="stMetricValue"]{color:var(--ink)}
[data-testid="stImage"] img{border-radius:14px}
.st-key-skincare-guidance{color:var(--ink)}
.st-key-skincare-guidance p,.st-key-skincare-guidance h4{color:var(--ink)}
.st-key-skincare-guidance [data-testid="stExpander"] details,.st-key-skincare-guidance summary{background:var(--surface);color:var(--ink);border-radius:12px}
.st-key-skincare-guidance [data-testid="stAlertContainer"]{background:var(--surface);color:var(--ink);border:1px solid var(--teal)}
.st-key-skincare-guidance a{color:var(--ink);text-decoration:underline}
.st-key-interactive-image [data-testid="stAlertContainer"]{background:var(--surface);border:1px solid var(--line);color:var(--ink)}
.st-key-interactive-image [data-testid="stAlertContainer"] p{color:var(--ink)}
.st-key-detection-summary [data-testid="stHorizontalBlock"]{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.6rem}
.st-key-detection-summary [data-testid="stColumn"]{width:100%!important;min-width:0!important}
.st-key-detection-summary [data-testid="stMetric"]{padding:.65rem}
.st-key-detection-summary [data-testid="stMetricLabel"] p{white-space:normal!important;overflow:visible!important;color:var(--ink)}
.st-key-detection-summary [data-testid="stMetricValue"]{font-size:1.8rem;color:var(--ink)}
[data-testid="stCaptionContainer"] p{color:var(--muted)!important}
.st-key-interactive-image summary{color:var(--ink);background:var(--surface)}
.st-key-image-preview img{max-height:480px;object-fit:contain;width:100%;border-radius:14px}
@media(max-width:900px){.st-key-detection-summary [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.st-key-image-preview img{max-height:360px}}
@media(max-width:640px){.block-container{padding:1.2rem 1rem}.hero{padding:1.25rem}.card{min-height:unset}h1{font-size:1.65rem!important}}
</style>
'''


@st.cache_resource(max_entries=1, show_spinner=False)
def service(environment):
    if environment == 'local':
        from .local_adapter import LocalAdapter
        return LocalAdapter()
    from .cloud_adapter import CloudAdapter
    return CloudAdapter(lambda name: st.secrets[name])


def appearance_css(choice):
    """Trusted session preference only; never interpolate uploaded content into CSS."""
    palettes = {
        'light': '--surface:#fff;--ink:#1F2937;--muted:#536579;--line:#dce5ef;--canvas:#F5F8FC;--teal:#0D9488;color-scheme:light;',
        'dark': '--surface:#152638;--ink:#edf4fc;--muted:#bac9da;--line:#334b63;--canvas:#0d1927;--teal:#5eead4;color-scheme:dark;',
    }
    if choice not in THEME_LABELS:choice = 'system'
    tokens = ':root{'+palettes[choice]+'}' if choice in palettes else ''
    return '<style>'+tokens+'''
    .stApp,[data-testid="stSidebar"]{color:var(--ink)}
    [data-testid="stExpander"] summary,[data-testid="stExpander"] details,
    [data-testid="stAlertContainer"], [role="listbox"], [role="option"],
    [data-testid="stSelectbox"] input,[data-testid="stNumberInput"] input{
        background:var(--surface)!important;color:var(--ink)!important}
    [data-testid="stAlertContainer"] p,[data-testid="stExpander"] summary p,
    [data-testid="stFileUploader"] p,[data-testid="stCaptionContainer"] p{color:var(--ink)!important}
    [data-testid="stButtonGroup"] button{background:var(--surface);color:var(--ink);border-color:var(--line)}
    [data-testid="stButtonGroup"] button[aria-pressed="true"]{background:#0f766e;color:white;border-color:#5eead4}
    </style>'''


def navigate(page):
    st.session_state['navigation'] = page


def clear_media():
    clear_concerns(st.session_state)
    for key in ('result', 'signature', 'result_time', 'image_verified', CACHE_SLOT):
        st.session_state.pop(key, None)
    st.session_state['upload_generation'] = st.session_state.get('upload_generation', 0)+1


def display_rows(rows):
    """Translate a copy for display; exported CSV and result schemas stay untouched."""
    return [{COLUMNS.get(k, k): (THAI.get(v, 'ไม่พบตำแหน่ง') if k == 'class_name' else
            (f'{v:.1%}' if k == 'confidence' and isinstance(v, (float, int)) else v))
            for k, v in row.items()} for row in rows]


def legend():
    st.markdown('<div class="legend">'+''.join(f'<span><i class="dot" style="background:{COLORS[c]}"></i>{THAI[c]}</span>' for c in CLASSES)+'</div>', unsafe_allow_html=True)


def home():
    st.markdown('''<section class="hero"><div class="eyebrow">โครงงานการเรียนรู้ของเครื่อง · SKN-1 (YOLO-NAS)</div>
    <h2>เข้าใจผลการตรวจจับ<br>ผ่านภาพและวิดีโอของคุณ</h2>
    <p>ระบบต้นแบบสำหรับตรวจจับลักษณะปัญหาผิวจากภาพและวิดีโอ โดยใช้เทคโนโลยี Machine Learning</p>
    <p>ตรวจจับ 4 ประเภท · ประมวลผลในระบบแอป · แสดงตำแหน่งที่ตรวจพบ</p></section>''', unsafe_allow_html=True)
    for col, label, page in zip(st.columns(3), ('เริ่มตรวจจับจากภาพ', 'ดูผลการทดสอบ', 'วิธีใช้งาน'), (PAGES[1], PAGES[3], PAGES[5])):
        col.button(label, on_click=navigate, args=(page,), width='stretch', type='primary' if page == PAGES[1] else 'secondary')
    st.subheader('ลักษณะปัญหาผิวที่ระบบตรวจจับ')
    descriptions = ('ตำแหน่งลักษณะสิวที่โมเดลตรวจพบจากภาพ', 'แนวเส้นริ้วรอยที่มองเห็นบนผิวหน้า', 'จุดหรือปื้นสีเข้มที่โมเดลตรวจพบ', 'บริเวณลักษณะรูขุมขนกว้างที่มองเห็น')
    for col, name, icon, description in zip(st.columns(4), CLASSES, ('◉', '≋', '◈', '⠿'), descriptions):
        with col:
            st.markdown(f'<div class="card"><span style="font-size:1.8rem;color:{COLORS[name]}">{icon}</span><h3>{THAI[name]}</h3><small>{name}</small><p>{description}</p></div>', unsafe_allow_html=True)
    st.subheader('ระบบทำงานอย่างไร')
    for col, number, title, detail in zip(st.columns(3), ('01', '02', '03'), ('อัปโหลดภาพหรือวิดีโอ', 'ระบบประมวลผลด้วยโมเดล AI', 'ดูตำแหน่งและจำนวนที่ตรวจพบ'), ('เลือกไฟล์ที่คุณมีสิทธิ์และได้รับความยินยอม', 'เริ่มวิเคราะห์เมื่อคุณกดปุ่มเท่านั้น', 'อ่านผลและดาวน์โหลดไฟล์สำหรับการสาธิต')):
        with col:st.markdown(f'<div class="card"><span class="badge">ขั้นตอน {number}</span><h3>{title}</h3><p>{detail}</p></div>', unsafe_allow_html=True)
    st.info('เริ่มต้นด้วยการตรวจจับจากภาพก่อนใช้วิดีโอบนระบบคลาวด์ การเปิดหน้านี้ยังไม่โหลดโมเดล')


def evaluation():
    st.subheader('ผลการทดสอบโมเดล')
    st.caption('ผลที่ตรวจสอบจากงานวิจัยเดิม · ชุดตรวจสอบ (Validation) ไม่ใช่ชุดทดสอบสุดท้าย (Test)')
    st.info('SKN-1 (YOLO-NAS) · Clean V2 · 315 ภาพ · 805 วัตถุ · 4 ประเภท')
    for col, label, value in zip(st.columns(4), ('mAP50', 'mAP50–95', 'ความแม่นยำ (Precision)', 'ความครอบคลุม (Recall)'), ('37.48%', '16.88%', '34.10%', '42.11%')):col.metric(label, value)
    st.metric('คะแนนสมดุลการตรวจจับ (Micro-F1)', '37.69%')
    st.caption('Precision / Recall / F1 ที่เกณฑ์ความเชื่อมั่น 0.25 และ IoU 0.50 · AP คำนวณจากผลที่เก็บตั้งแต่ 0.001 โดยใช้ COCO maxDet 300')
    values = ((.315984,.109483,.357311,.412807,.383059),(.363720,.147379,.152941,.590909,.242991),(.527176,.313920,.6,.5625,.580645),(.292375,.104302,.304348,.424242,.354430))
    st.dataframe([dict(zip(('ประเภท','AP50','AP50–95','ความแม่นยำ','ความครอบคลุม','F1'), (THAI[c], *(f'{x:.2%}' for x in v)))) for c,v in zip(CLASSES, values)], hide_index=True, width='stretch')
    st.warning('คลาสมีจำนวนตัวอย่างไม่สมดุล และการตรวจคุณภาพคำอธิบายกำกับยังมีข้อจำกัด ผลบนชุดตรวจสอบไม่รับประกันผลกับภาพใหม่ และไม่ได้เป็นหลักฐานความแม่นยำทางการแพทย์')
    with st.expander('แหล่งข้อมูลและเงื่อนไขการประเมิน'):
        st.write('หลักฐานจากโครงงานต้นฉบับ:')
        st.code('results/skn1_optimization/20261023T101106Z_nms30_c2ce10e9b2/\nbaseline_metrics.json\nper_class_baseline.csv\nthreshold_comparison.csv', language=None)
        st.write('ONNX CPU · NMS IoU 0.30 · เก็บผลตั้งแต่ความเชื่อมั่น 0.001 · จำนวนผลสูงสุด 300 · COCO IoU 0.50–0.95')
        st.write('หน้านี้สรุปเฉพาะค่าที่ตรวจสอบแล้ว ไม่ได้คัดลอกชุดข้อมูลหรือไฟล์ผลทดลองเข้าระบบเผยแพร่')
    st.caption('ผลเปรียบเทียบโมเดลบนชุดข้อมูลเดียวกันและผลชุดทดสอบสุดท้าย: ยังไม่มีข้อมูลที่ยืนยันได้ในชุดเผยแพร่นี้')
    st.caption('ไม่มีกราฟการเรียนรู้ของ SKN-1 เนื่องจากโครงงานไม่ได้ฝึกโมเดลนี้')


def about():
    st.subheader('เกี่ยวกับโครงงาน')
    st.write('โครงงานระบบตรวจจับปัญหาผิวด้วยปัญญาประดิษฐ์ พัฒนาขึ้นเพื่อสาธิตการประยุกต์ใช้การตรวจจับวัตถุกับภาพและวิดีโอ')
    with st.container(border=True):
        st.markdown('**วัตถุประสงค์**\n\nแสดงตำแหน่งและจำนวนลักษณะปัญหาผิว 4 ประเภท พร้อมนำเสนอผลการทดลองอย่างตรวจสอบได้')
        st.markdown('**เทคโนโลยี**\n\nPython · Streamlit · SKN-1 (YOLO-NAS) · ONNX Runtime (CPU) · การประมวลผลวิดีโอด้วย PyAV')
        st.markdown('**กระบวนการ**\n\nรับไฟล์ → ตรวจข้อจำกัด → ตรวจจับด้วยโมเดล → แสดงกรอบและตาราง → ดาวน์โหลดผล')
    st.warning('คุณภาพภาพ แสง มุมกล้อง ขนาดเป้าหมาย และความแตกต่างของข้อมูล อาจทำให้ระบบพลาดหรือแสดงตำแหน่งผิดได้')
    st.write('ไม่มีการฝึกหรือปรับน้ำหนัก SKN-1 ในแอปนี้ ไม่มีการอนุมานสาเหตุของปัญหาผิวจากภาพ')
    st.caption('สิทธิ์การเผยแพร่บริการโมเดลออนไลน์ยังอยู่ระหว่างการยืนยัน การปรับหน้าจอรอบนี้ไม่ได้เปิดบริการใหม่')


def help_page():
    st.subheader('คำแนะนำการใช้งาน')
    with st.expander('ตรวจจับจากภาพ', expanded=True):
        st.markdown('1. ไปที่ **ตรวจจับจากภาพ**\n2. อัปโหลด JPG, JPEG หรือ PNG ไม่เกิน 5 MB (5 MiB) และ 4 ล้านพิกเซลโดยประมาณ\n3. เลือกรูปแบบการคัดกรอง แล้วกด **เริ่มตรวจจับปัญหาผิว**\n4. อ่านผลจากกรอบ สี และตาราง แล้วดาวน์โหลดผลตามต้องการ')
    with st.expander('ตรวจจับจากวิดีโอ', expanded=True):
        st.markdown('1. บนคลาวด์ ให้ตรวจจับภาพสำเร็จในรอบการใช้งานนี้ก่อน\n2. เลือก MP4 ไม่เกิน 20 MB (20 MiB), 12 วินาที, ด้านยาว 1280 พิกเซล และพิกเซลรวมไม่เกิน 1280 × 720\n3. กด **เริ่มวิเคราะห์วิดีโอ** แล้วรอจนเสร็จ\n4. ดูผลรายเฟรม และดาวน์โหลดวิดีโอตัวอย่างหรือข้อมูล CSV')
        st.caption('ตรวจตัวอย่าง 1 เฟรมต่อวินาที ไม่ตรวจทุกเฟรม ไม่ใช่ระบบเรียลไทม์ วิดีโอผลลัพธ์ไม่มีเสียง')
    with st.expander('ไม่พบตำแหน่ง หมายความว่าอย่างไร?'):
        st.write('หมายถึงไม่มีผลที่ผ่านเกณฑ์ของโมเดล ไม่ได้หมายความว่าผิวปกติ ลองใช้ภาพชัด แสงสม่ำเสมอ และหลีกเลี่ยงภาพที่มีตัวกรอง')
    with st.expander('รูปแบบสมดุลต่างจากเน้นความแม่นยำอย่างไร?'):
        st.write('สมดุลใช้เกณฑ์ 0.25 ทุกประเภท ส่วนเน้นความแม่นยำเพิ่มเกณฑ์บางประเภทเพื่อลดผลความเชื่อมั่นต่ำ แต่อาจพลาดเป้าหมายมากขึ้น โดยเฉพาะริ้วรอย')
    with st.expander('ข้อมูลของฉันถูกเก็บอย่างไร?'):
        st.write('ไฟล์ประมวลผลในระบบแอป ไม่ส่งภาพไปบริการตรวจจับภายนอก ผลลัพธ์อยู่ในรอบการใช้งานชั่วคราว กดล้างข้อมูลเมื่อเสร็จ การล้างไม่ใช่การรับรองการลบข้อมูลอย่างกู้คืนไม่ได้')
    st.info(DISCLAIMER)


def skincare_guidance_view(counts, *, showcase=False, input_kind='image', identity=None):
    """Static presentation only. Never calls service, SDK, or an external API."""
    with st.container(key='skincare-guidance'):
        _skincare_guidance_content(counts, showcase=showcase, input_kind=input_kind, identity=identity)


def _skincare_guidance_content(counts, *, showcase=False, input_kind='image', identity=None):
    st.subheader('ตัวอย่างคำแนะนำที่ระบบสามารถแสดงได้' if showcase else 'คำแนะนำการดูแลผิวเบื้องต้น')
    if showcase:
        st.caption('ข้อมูลสาธิตเท่านั้น ไม่ใช่ผลวิเคราะห์ภาพจริง และไม่ได้สร้างผลตรวจจับ')
    else:
        st.caption('อ่านข้อมูลจากผล AI หรือเลือกหัวข้อที่สนใจเพิ่มเติมได้ โดยผลตรวจจับจะไม่เปลี่ยน')
    st.info(MEDICAL_DISCLAIMER)
    st.caption(CONCERN_DISCLAIMER)
    ai_topics = guidance_topics(counts) if not showcase else ()
    ai_slot = st.container()
    key = concern_session_key(st.session_state, 'showcase' if showcase else input_kind, identity)
    with st.container(border=True):
        st.markdown('#### มีปัญหาผิวอื่นที่คุณกังวลหรือไม่?')
        st.caption('หากมีลักษณะปัญหาผิวที่คุณกังวล แต่ระบบตรวจไม่พบ สามารถเลือกหัวข้อที่ต้องการศึกษาเพิ่มเติมได้')
        labels = dict(THAI, **{OTHER_CONCERN:'อื่น ๆ / ไม่แน่ใจ'})
        concerns = selected_concerns(st.multiselect('เลือกหัวข้อที่คุณสนใจ', CONCERN_OPTIONS,
            format_func=labels.get, key=key, placeholder='เลือกได้หลายหัวข้อ'))
    origins = guidance_origins(counts, concerns, showcase=showcase)
    with ai_slot:
        if ai_topics:
            st.markdown('#### ข้อมูลจากผล AI')
            for name in ai_topics:_guidance_topic(name, origins[name])
        elif not showcase:
            st.write(NO_DETECTION_MESSAGE)
    extras = tuple(name for name, origin in origins.items() if origin == 'user')
    if extras or OTHER_CONCERN in concerns:
        st.markdown('#### หัวข้อที่คุณเลือกศึกษาด้วยตนเอง')
        st.caption('คำแนะนำเพิ่มเติมสำหรับคุณ · ผู้ใช้เลือกเอง ไม่ได้เพิ่มผลตรวจจับของ AI')
        for name in extras:_guidance_topic(name, 'user')
    if showcase:
        for name in guidance_topics({}, showcase=True):
            if name not in origins:_guidance_topic(name, 'showcase')
    if (not ai_topics and not extras and not showcase) or OTHER_CONCERN in concerns:
        with st.container(border=True):
            st.markdown('#### การดูแลผิวทั่วไป')
            if OTHER_CONCERN in concerns:st.caption('ผู้ใช้เลือกเอง · อื่น ๆ / ไม่แน่ใจ')
            for line in GENERAL_CARE:st.markdown(f'- {line}')
    st.caption(INGREDIENT_CAUTION)
    if len(origins) > 1:st.caption('การเลือกหรือพบหลายหัวข้อไม่ได้หมายความว่ามีโรคหลายชนิด และไม่ควรรวมสารทุกชนิดเป็นชุดรักษา')
    # Shared once, rather than repeated as a supposed treatment for each detected class.
    st.caption(NUTRITION_DISCLAIMER)
    with st.expander('สารอาหารที่มีส่วนช่วยดูแลสุขภาพผิว'):
        st.write('ตัวอย่างอาหารสำหรับโภชนาการทั่วไป เลือกให้เหมาะกับข้อจำกัดด้านสุขภาพและการแพ้อาหารของตนเอง ไม่ใช่คำแนะนำให้ซื้ออาหารเสริม')
        for nutrient, text in NUTRIENTS:st.markdown(f'- **{nutrient}**: {text}')
        st.caption('อาหารไม่ใช่สิ่งที่รับประกันว่าจะรักษาลักษณะผิวที่ตรวจพบได้ และระบบไม่แนะนำขนาดวิตามินหรือยาเฉพาะบุคคล')
        st.markdown('**อ่านข้อมูลเพิ่มเติมจากแหล่งอ้างอิง**')
        for title, url in NUTRITION_REFERENCES:st.markdown(f'- [{title}]({url})')


def _guidance_topic(name, origin):
    guidance = SKINCARE_GUIDANCE[name]
    badges = {'ai':'AI ตรวจพบ', 'user':'ผู้ใช้เลือกเอง',
              'both':'AI ตรวจพบ · ผู้ใช้สนใจเพิ่มเติม', 'showcase':'ข้อมูลสาธิตเพื่อการศึกษา'}
    with st.expander(guidance['title_th']):
        st.caption(badges[origin])
        st.write(context_intro(name, origin))
        for key, title in (('daily_care','การดูแลผิวหน้า'),
            ('skincare_ingredients','ผลิตภัณฑ์และสารบำรุงที่ควรรู้จัก'), ('nutrition','อาหารและสารอาหาร'),
            ('exercise_lifestyle','การออกกำลังกายและการใช้ชีวิต'), ('cautions','ข้อควรระวัง'),
            ('when_to_seek_professional_care','เมื่อควรปรึกษาผู้เชี่ยวชาญ')):
            st.markdown(f'#### {title}')
            for line in guidance[key]:st.markdown(f'- {line}')
        st.markdown('**อ่านข้อมูลเพิ่มเติมจากแหล่งอ้างอิง**')
        for title, url in guidance['references']:st.markdown(f'- [{title}]({url})')


def preview_image(image, caption):
    """Bound display dimensions only; never touch inference or download pixels."""
    from .presentation import preview_thumbnail
    with st.container(key='image-preview'):
        st.image(preview_thumbnail(image), caption=caption, width='stretch', output_format='PNG')


def summary_cards(counts):
    with st.container(key='detection-summary'):
        for col, name in zip(st.columns(4), CLASSES):
            col.metric(THAI[name], str(counts[name]))
    st.caption('จำนวนตำแหน่งที่ผ่านเกณฑ์การแสดงผล')


def results_view(result, kind, *, allow_reset=True):
    st.subheader('ผลการตรวจจับ')
    st.success('ประมวลผลสำเร็จ')
    summary_cards(result['counts'])
    legend()
    if not any(result['counts'].values()):
        st.info('ไม่พบตำแหน่งที่ผ่านเกณฑ์การตรวจจับ การไม่พบตำแหน่งปัญหาผิว ไม่ได้หมายความว่าผิวปกติ')
    if kind == 'image':
        st.image(result['image_bytes'], caption='ภาพผลการตรวจจับ', width='stretch', output_format='PNG')
        st.download_button('ดาวน์โหลดภาพผลลัพธ์', result['image_bytes'], 'skn_annotated.png', 'image/png', width='stretch')
    else:
        st.video(result['video_bytes'], format='video/mp4')
        st.caption('วิดีโอผลลัพธ์แสดงเฉพาะเฟรมตัวอย่าง 1 เฟรมต่อวินาที พร้อมเวลาเดิม ไม่มีเสียง')
        with st.expander('ผลแต่ละเฟรม'):
            st.dataframe(display_rows(result['frames']), hide_index=True, width='stretch')
        st.caption(f"เวลาประมวลผลวิดีโอรวม {result.get('processing_seconds', 0):.2f} วินาที")
        st.download_button('ดาวน์โหลดวิดีโอผลลัพธ์', result['video_bytes'], 'skn_sampled.mp4', 'video/mp4', width='stretch')
    with st.expander('คำแนะนำการดูแลผิว'):
        skincare_guidance_view(result['counts'], input_kind=kind, identity=st.session_state.get('signature'))
    with st.expander('ตารางตำแหน่งตรวจจับ'):
        if result['predictions']:
            st.dataframe(display_rows(result['predictions']), hide_index=True, width='stretch')
    st.download_button('ดาวน์โหลดข้อมูล CSV', result['csv_bytes'], 'skn_detections.csv', 'text/csv', width='stretch')
    st.caption(f"SKN-1 · เวลาที่ใช้ตรวจจับ {result['inference_seconds']:.2f} วินาที · ประมวลผลด้วย CPU")
    with st.expander('ข้อมูลการทำงานและหน่วยความจำ'):
        st.write('การโหลดโมเดลครั้งแรกอาจใช้เวลามากกว่าการตรวจจับครั้งต่อไป ข้อจำกัดทรัพยากรของผู้ให้บริการยังมีผล')
        if result.get('model_load_seconds') is not None:
            st.caption(f"เวลาโหลดโมเดล {result['model_load_seconds']:.2f} วินาที (ไม่ใช่เวลาประมวลผลต่อภาพ)")
    if allow_reset:st.button('ตรวจจับภาพใหม่' if kind == 'image' else 'วิเคราะห์วิดีโอใหม่', on_click=clear_media)


def reset_image_display(prefix):
    st.session_state[prefix+'mode'] = 'Balanced'
    st.session_state[prefix+'threshold'] = 25
    st.session_state[prefix+'opacity'] = 65
    st.session_state[prefix+'labels'] = 'class_percent'


@st.fragment
def interactive_image_results(key):
    with st.container(key='interactive-image'):
        _interactive_image_results(key)


def change_confidence(prefix):
    st.session_state[prefix+'mode'] = CUSTOM


def _interactive_image_results(key):
    cache = get_image_cache(st.session_state, key, time.time())
    if cache is None:
        clear_concerns(st.session_state, 'image')
        st.info('ผลตรวจจับหมดอายุหรือถูกล้าง กรุณากดเริ่มตรวจจับอีกครั้ง');return
    prefix = 'image-display-'+key+'-'
    st.session_state.setdefault(prefix+'mode','Balanced')
    st.session_state.setdefault(prefix+'threshold',25)
    st.session_state.setdefault(prefix+'opacity',65)
    # Render controls into placeholders while keeping summary and image first on mobile.
    st.subheader('ผลการตรวจจับ')
    summary = st.container()
    image_column, control_column = st.columns([1.5,1], gap='medium')
    with image_column:
        selected = st.radio('เลือกภาพที่ต้องการดู', ['ภาพผลตรวจจับ','ภาพต้นฉบับ'], horizontal=True, key=prefix+'image')
        image_slot = st.container()
    with control_column:
        profile = st.session_state[prefix+'mode']
        if profile == 'Balanced':st.session_state[prefix+'threshold'] = 25
        st.slider('ระดับความเชื่อมั่นขั้นต่ำ', min_value=10, max_value=90, step=1, format='%d%%',
            key=prefix+'threshold', disabled=profile=='Precision-focused', on_change=change_confidence, args=(prefix,))
        st.caption('ลดค่าเพื่อแสดงตำแหน่งมากขึ้น เพิ่มค่าเพื่อคัดกรองเข้มงวดขึ้น')
        if profile == 'Precision-focused':st.caption('ใช้เกณฑ์รายประเภทตามโหมดเน้นความแม่นยำ เลือกกำหนดเกณฑ์เองเพื่อปรับ Slider')
        with st.expander('ตั้งค่าขั้นสูง'):
            labels = dict(PROFILE_LABELS, **{CUSTOM:'กำหนดเกณฑ์เอง'})
            profile = st.selectbox('รูปแบบการคัดกรองผลตรวจจับ', list(labels), format_func=labels.get, key=prefix+'mode')
            opacity = st.slider('ความเข้มของกรอบตรวจจับ', min_value=10,max_value=100,step=1,format='%d%%',key=prefix+'opacity')/100
            label_names={'class_percent':'ชื่อประเภทและเปอร์เซ็นต์','percent':'เปอร์เซ็นต์เท่านั้น','none':'ซ่อนข้อความ'}
            label_mode=st.selectbox('การแสดงข้อความบนกรอบ',list(label_names),format_func=label_names.get,key=prefix+'labels')
            st.button('รีเซ็ตการแสดงผล',on_click=reset_image_display,args=(prefix,))
        threshold=st.session_state[prefix+'threshold']/100
        if profile == CUSTOM and threshold < .20:
            st.warning('เกณฑ์ต่ำอาจทำให้ตรวจจับผิดพลาดมากขึ้น')
        st.caption('สมดุล 25%' if profile=='Balanced' else ('กำหนดเกณฑ์เอง' if profile==CUSTOM else 'เน้นความแม่นยำของผลที่แสดง'))
    try:
        image=decode_image(cache['original_bytes'])
        view=build_image_result(image,cache['candidates'],display_thresholds(profile,threshold),opacity,label_mode)
        view.update(cache['metadata'])
    except AppError as error:st.error(MESSAGES[error.code]);return
    with summary:
        summary_cards(view['counts'])
        if not any(view['counts'].values()):st.info('ไม่พบตำแหน่งที่ผ่านเกณฑ์ ผลนี้ไม่ได้ยืนยันว่าผิวไม่มีปัญหา')
    with image_slot:
        if selected=='ภาพต้นฉบับ':preview_image(image,'ภาพต้นฉบับ')
        else:
            import io
            from PIL import Image
            preview_image(Image.open(io.BytesIO(view['image_bytes'])),'ภาพผลตรวจจับ')
    st.markdown('#### ดาวน์โหลดผลลัพธ์')
    png,csv=st.columns(2)
    png.download_button('ดาวน์โหลดภาพ PNG',view['image_bytes'],'skn_annotated.png','image/png',width='stretch')
    csv.download_button('ดาวน์โหลดข้อมูล CSV',view['csv_bytes'],'skn_detections.csv','text/csv',width='stretch')
    with st.expander('ตารางตำแหน่งตรวจจับ'):
        legend()
        if view['predictions']:st.dataframe(display_rows(view['predictions']),hide_index=True,width='stretch')
        else:st.write('ไม่มีตำแหน่งที่ผ่านเกณฑ์')
    with st.expander('คำแนะนำการดูแลผิว'):
        skincare_guidance_view(view['counts'], input_kind='image', identity=key)
    with st.expander('รายละเอียดทางเทคนิค'):
        st.write('SKN-1 · ONNX CPU · NMS IoU 0.30 · สูงสุด 300 ตำแหน่ง · เก็บผลเฉพาะ Session 600 วินาที')
        st.caption('Candidates ผ่าน NMS และการจำกัดจำนวนแล้ว ไม่สามารถกู้กล่องที่ถูกตัดทิ้งได้ การปรับหน้าจอไม่เรียกโมเดลซ้ำ Slider อัปเดตเมื่อปล่อยเมาส์')
        st.caption('เกณฑ์ความเชื่อมั่นต่ำอาจทำให้แสดงตำแหน่งที่ไม่ถูกต้องจำนวนมาก ผลนี้เหมาะสำหรับการสำรวจการทำงานของโมเดล ไม่ใช่การยืนยันปัญหาผิว')
        st.caption(f"เวลาตรวจจับ {view['inference_seconds']:.2f} วินาที · ข้อความบนภาพใช้ภาษาอังกฤษ พร้อมคำอธิบายสีภาษาไทย")
    if st.button('ตรวจจับภาพใหม่'):
        clear_media();st.rerun(scope='app')


def detection(kind, environment):
    st.subheader('ตรวจจับปัญหาผิวจากภาพ' if kind == 'image' else 'ตรวจจับปัญหาผิวจากวิดีโอ')
    st.caption('อัปโหลดภาพใบหน้าเพื่อให้ระบบตรวจจับลักษณะปัญหาผิว' if kind=='image' else 'อัปโหลดวิดีโอ → เริ่มวิเคราะห์ → ดูผลและดาวน์โหลด')
    if kind == 'image':
        cached = get_image_cache(st.session_state, now=time.time())
        if cached is not None:
            interactive_image_results(cached['key'])
            return
    left, right = st.columns([1, 1.6], gap='medium')
    with left:
        with st.container(border=True):
            st.markdown('### อัปโหลดรูปภาพ' if kind == 'image' else '### อัปโหลดวิดีโอ')
            st.caption('รองรับ JPG, JPEG และ PNG ขนาดไม่เกิน 5 MB (5 MiB) · ไม่เกิน 4 ล้านพิกเซลโดยประมาณ' if kind == 'image' else
                       'รองรับ MP4 ไม่เกิน 20 MB (20 MiB) · 12 วินาที · ด้านยาวไม่เกิน 1280 พิกเซล · พิกเซลรวมไม่เกิน 1280 × 720')
            if kind == 'video':st.info('วิเคราะห์ตัวอย่าง 1 เฟรมต่อวินาที ไม่ใช่ระบบตรวจจับแบบเรียลไทม์')
            uploaded = st.file_uploader('เลือกไฟล์รูปภาพ' if kind == 'image' else 'เลือกไฟล์วิดีโอ', type=['jpg', 'jpeg', 'png'] if kind == 'image' else ['mp4'], key=f"upload-{kind}-{st.session_state.get('upload_generation',0)}", max_upload_size=(LIMITS.image_bytes if kind == 'image' else LIMITS.video_bytes)//1024**2)
            profile = 'Balanced'
            if kind == 'video':
                with st.expander('ตั้งค่าขั้นสูง'):
                    profile = st.selectbox('รูปแบบการคัดกรองผลตรวจจับ', list(PROFILES), format_func=PROFILE_LABELS.get, key=f'profile-{kind}')
                st.caption('วิดีโอใช้เกณฑ์ที่เลือกตอนเริ่มงาน ไม่มี Slider แบบภาพ การเปลี่ยนเกณฑ์ต้องเริ่มงานใหม่เอง')

            st.caption('ใช้เฉพาะไฟล์ที่คุณมีสิทธิ์และได้รับความยินยอม ไม่อัปโหลดข้อมูลส่วนบุคคลที่ไม่จำเป็น')
    with right:
        if uploaded is None:
            clear_concerns(st.session_state, kind)
            st.session_state.pop(CACHE_SLOT, None)
            st.markdown('<div class="empty"><h3>พร้อมเริ่มต้นเมื่อคุณเลือกไฟล์</h3><p>ภาพตัวอย่างและผลการตรวจจับจะแสดงในบริเวณนี้<br>ระบบยังไม่โหลดโมเดลจนกว่าคุณจะเริ่มตรวจจับ</p></div>', unsafe_allow_html=True)
            return
        if uploaded.size > (LIMITS.image_bytes if kind == 'image' else LIMITS.video_bytes):
            if kind == 'image':st.session_state.pop(CACHE_SLOT, None)
            st.error(MESSAGES['UPLOAD_TOO_LARGE']);return
        data = uploaded.getvalue()
        signature = candidate_cache_key(data) if kind == 'image' else (kind, hashlib.sha256(data).hexdigest(), profile)
        if kind == 'image':get_image_cache(st.session_state, signature, time.time())
        if st.session_state.get('signature') != signature:
            st.session_state.pop('result', None)
            clear_concerns(st.session_state, kind)
        if kind == 'image':
            try:decode_image(data)
            except AppError as error:st.error(MESSAGES[error.code]);return
            if get_image_cache(st.session_state, signature, time.time()) is None and st.button('เปลี่ยนภาพ'):
                clear_media();st.rerun()
        else:st.video(data, format='video/mp4')
        blocked = environment == 'cloud' and kind == 'video' and not st.session_state.get('image_verified')
        if blocked:st.warning(MESSAGES['VIDEO_IMAGE_FIRST'])
        completed = kind=='image' and get_image_cache(st.session_state,signature,time.time()) is not None
        clicked = not completed and st.button('เริ่มตรวจจับปัญหาผิว' if kind == 'image' else 'เริ่มวิเคราะห์วิดีโอ', type='primary', disabled=blocked, width='stretch')
        if kind == 'image' and not completed:preview_image(decode_image(data), 'ภาพที่เลือก')
        if clicked:
            st.session_state.pop('result', None);st.session_state.pop('signature', None)
            if kind == 'image':st.session_state.pop(CACHE_SLOT, None)
            progress = st.progress(0., text='กำลังเตรียมระบบและตรวจสอบไฟล์…')
            try:
                with st.spinner('ระบบกำลังวิเคราะห์รูปภาพ กรุณารอสักครู่...' if kind == 'image' else 'ระบบกำลังวิเคราะห์วิดีโอ กรุณารอสักครู่...'):
                    result = service(environment).process_media(data, kind, profile,
                        lambda done,total: progress.progress(min(1.,done/max(total,1)), text=f'กำลังประมวลผลเฟรมที่ {done} จาก {total}'))
                if kind == 'image':
                    st.session_state[CACHE_SLOT] = make_image_cache(data, result, time.time())
                    st.session_state.update(signature=signature, result_time=time.time())
                else:st.session_state.update(result=result, signature=signature, result_time=time.time())
                if kind == 'image':st.session_state['image_verified'] = True
                progress.progress(1., text='ประมวลผลสำเร็จ')
                if kind == 'image':st.rerun()
            except AppError as error:progress.empty();st.error(MESSAGES[error.code])
            except Exception:progress.empty();st.error(MESSAGES['INFERENCE_FAILED'])
        if kind == 'video':
            result = st.session_state.get('result') if st.session_state.get('signature') == signature else None
            if result is not None:results_view(result, kind)
    if kind == 'image' and get_image_cache(st.session_state, signature, time.time()) is not None:
        interactive_image_results(signature)


def main():
    st.set_page_config(page_title='ระบบตรวจจับปัญหาผิว · SKN-1', page_icon='🔬', layout='wide')
    st.markdown(CSS, unsafe_allow_html=True)  # Fixed trusted markup only; never interpolate uploads.
    st.markdown(appearance_css(st.session_state.get('appearance','system')), unsafe_allow_html=True)
    environment = mode()
    get_image_cache(st.session_state, now=time.time())
    if time.time()-st.session_state.get('result_time', 0) > LIMITS.result_ttl_seconds:
        clear_concerns(st.session_state)
        st.session_state.pop('result', None);st.session_state.pop('signature', None)
    with st.sidebar:
        st.markdown('### ◈ วิเคราะห์ผิวด้วย AI')
        st.caption('SKN-1 · โครงงานการเรียนรู้ของเครื่อง')
        st.segmented_control('สีหน้าจอ', list(THEME_LABELS), format_func=THEME_LABELS.get,
            default='system', selection_mode='single', key='appearance', width='stretch')
        page = st.radio('เมนูหลัก', PAGES, key='navigation')
        st.divider()
        st.caption('การเปิดหน้าเว็บยังไม่โหลดโมเดล การตรวจจับเริ่มเมื่อกดปุ่มเท่านั้น')
        st.button('ล้างข้อมูลการใช้งาน', on_click=clear_media, width='stretch')
        st.markdown('[ข้อมูลโมเดล](https://universe.roboflow.com/skn-f1vaw/skn-1) · [ข้อมูลสิทธิ์การใช้งาน](https://github.com/Deci-AI/super-gradients/blob/master/LICENSE.YOLONAS.md)')
    st.title('ระบบตรวจจับปัญหาผิวด้วยปัญญาประดิษฐ์')
    st.caption('SKN-1 (YOLO-NAS) · ระบบต้นแบบสำหรับการศึกษา')
    if page == PAGES[0]:home()
    elif page == PAGES[1]:detection('image', environment)
    elif page == PAGES[2]:detection('video', environment)
    elif page == PAGES[3]:evaluation()
    elif page == PAGES[4]:about()
    else:help_page()
    st.divider()
    st.caption(DISCLAIMER)
    st.caption('การไม่พบตำแหน่งปัญหาผิว ไม่ได้หมายความว่าผิวปกติ')
