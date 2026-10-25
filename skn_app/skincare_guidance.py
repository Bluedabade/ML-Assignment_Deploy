"""Source-checked static Thai education, selected by canonical counts; no runtime access.

Sources checked 2026-10-24. This module performs no requests and prescribes no regimen.
"""
from collections.abc import Mapping
import math
from numbers import Real

from .config import CLASSES

CONTENT_VERSION = '2026-10-25.1'
MEDICAL_DISCLAIMER = 'คำแนะนำนี้จัดทำขึ้นเพื่อให้ความรู้เบื้องต้นตามหัวข้อที่ระบบ AI ตรวจพบหรือผู้ใช้เลือกศึกษาด้วยตนเอง ไม่ใช่การวินิจฉัยโรค การประเมินภาวะขาดสารอาหาร หรือคำแนะนำการรักษาเฉพาะบุคคล หากมีอาการผิดปกติ รุนแรง หรือกังวลเกี่ยวกับสุขภาพผิว ควรปรึกษาแพทย์ผิวหนัง'
NUTRITION_DISCLAIMER = 'ระบบไม่สามารถระบุได้ว่าร่างกายขาดวิตามินหรือสารอาหารใดจากภาพใบหน้า ข้อมูลนี้เป็นเพียงคำแนะนำด้านโภชนาการทั่วไป ไม่ใช่ผลการประเมินภาวะโภชนาการ'
NO_DETECTION_MESSAGE = 'ระบบไม่พบลักษณะปัญหาผิวที่ผ่านเกณฑ์การตรวจจับ คุณสามารถศึกษาคำแนะนำการดูแลผิวทั่วไปได้ แต่ผลนี้ไม่ได้ยืนยันว่าผิวไม่มีปัญหา'
RETINOID_CAUTION = 'ห้ามใช้ Retinol / Retinoids ระหว่างตั้งครรภ์หรือวางแผนตั้งครรภ์ หากให้นมบุตรหรือไม่แน่ใจ ควรปรึกษาแพทย์หรือเภสัชกรก่อนใช้'
INGREDIENT_CAUTION = 'รายชื่อสารเป็นข้อมูลเพื่อการศึกษา ไม่ใช่ชุดรักษาที่ต้องใช้ร่วมกัน ไม่ควรเริ่มสารออกฤทธิ์หลายชนิดพร้อมกัน และควรอ่านฉลากหรือปรึกษาผู้เชี่ยวชาญก่อนใช้'
CONCERN_DISCLAIMER = 'ข้อมูลการดูแลผิวนี้จัดทำขึ้นเพื่อการศึกษา โดยอ้างอิงหัวข้อที่ระบบ AI ตรวจพบหรือผู้ใช้เลือกศึกษาด้วยตนเอง ไม่ใช่การวินิจฉัยโรค การยืนยันปัญหาผิว หรือคำแนะนำการรักษาเฉพาะบุคคล'
OTHER_CONCERN = 'other_unsure'  # Presentation option only; never a model class.
CONCERN_OPTIONS = (*CLASSES, OTHER_CONCERN)
CONCERN_NAMES = dict(zip(CLASSES, ('สิว', 'ริ้วรอย', 'จุดด่างดำ', 'รูขุมขนกว้าง')))


def selected_concerns(values):
    """Ignore unsupported input safely, retaining canonical order and no duplicates."""
    if not isinstance(values, (list, tuple, set, frozenset)):return ()
    return tuple(name for name in CONCERN_OPTIONS if name in values)


def guidance_origins(counts, concerns=(), *, showcase=False):
    detected = () if showcase else detected_classes(counts)
    chosen = selected_concerns(concerns)
    return {name: ('both' if name in detected and name in chosen else
                   'ai' if name in detected else 'user')
            for name in CLASSES if name in detected or name in chosen}


def context_intro(name, origin):
    label = CONCERN_NAMES.get(name)
    if label is None or origin not in ('ai', 'user', 'both', 'showcase'):return ''
    if origin == 'showcase':return f'ตัวอย่างข้อมูลความรู้เกี่ยวกับ{label} ไม่ใช่ผลวิเคราะห์ภาพจริง'
    if origin == 'user':return f'คุณเลือกศึกษาข้อมูลเกี่ยวกับ{label} แม้ระบบ AI อาจไม่ได้ตรวจพบลักษณะดังกล่าว ข้อมูลต่อไปนี้เป็นคำแนะนำการดูแลผิวเบื้องต้น'
    return f'ระบบ AI พบลักษณะภาพที่สอดคล้องกับ{label} คำแนะนำต่อไปนี้เป็นข้อมูลทั่วไป ไม่ใช่การวินิจฉัย'


def concern_session_key(state, kind, identity):
    """Bind selections to one active file per input kind, without storing media."""
    if kind not in ('image', 'video', 'showcase'):raise ValueError('INVALID_CONCERN_SCOPE')
    key, marker = 'care-'+kind, '_care_identity_'+kind
    if marker not in state or state[marker] != identity:
        state.pop(key, None)
        state[marker] = identity
    return key


def clear_concerns(state, kind=None):
    for item in (('image','video','showcase') if kind is None else (kind,)):
        state.pop('care-'+item, None)
        state.pop('_care_identity_'+item, None)

AAD = 'https://www.aad.org/public/'
RETINOID_REFERENCE = ('ข้อมูลเรื่อง Retinol และ Retinoids จากสมาคมแพทย์ผิวหนังสหรัฐฯ', AAD+'everyday-care/skin-care-secrets/anti-aging/retinoid-retinol')
PREGNANCY_REFERENCE = ('การดูแลผิวระหว่างตั้งครรภ์จากสมาคมแพทย์ผิวหนังสหรัฐฯ', AAD+'everyday-care/skin-care-secrets/routine/pregnancy-skin-care')

GENERAL_CARE = (
    'ทำความสะอาดผิวอย่างอ่อนโยน ไม่ขัดถูแรง และเลือกมอยส์เจอไรเซอร์ที่เหมาะกับผิว',
    'ป้องกันแดดด้วยเสื้อผ้า หมวก และครีมกันแดดชนิด Broad-spectrum SPF 30 ขึ้นไป',
    'หากผลิตภัณฑ์ทำให้แสบ แดง หรือระคายเคือง ควรหยุดใช้และปรึกษาผู้เชี่ยวชาญเมื่ออาการไม่ดีขึ้น',
)
NUTRIENTS = (
    ('วิตามินซี', 'ฝรั่ง ส้ม และพริกหวาน เป็นตัวอย่างแหล่งอาหาร วิตามินซีมีบทบาทในการสร้างคอลลาเจนตามปกติ'),
    ('วิตามินอี', 'พบในถั่ว เมล็ดพืช และน้ำมันพืชบางชนิด'),
    ('โปรตีน', 'เลือกจากไข่ ปลา เนื้อสัตว์ เต้าหู้ และถั่ว ตามความเหมาะสม'),
    ('สังกะสี', 'พบในเนื้อสัตว์ อาหารทะเล ถั่ว และธัญพืช'),
    ('ไขมันจำเป็น', 'ปลา ถั่วบางชนิด และเมล็ดพืช เป็นตัวอย่างแหล่งไขมันที่เป็นประโยชน์'),
)
NUTRITION_REFERENCES = (
    ('ข้อมูลวิตามินซีจากสถาบันสุขภาพแห่งชาติสหรัฐฯ', 'https://ods.od.nih.gov/factsheets/VitaminC-Consumer/'),
    ('ข้อมูลวิตามินอีจากสถาบันสุขภาพแห่งชาติสหรัฐฯ', 'https://ods.od.nih.gov/factsheets/VitaminE-Consumer/'),
    ('ข้อมูลสังกะสีจากสถาบันสุขภาพแห่งชาติสหรัฐฯ', 'https://ods.od.nih.gov/factsheets/Zinc-Consumer/'),
    ('ข้อมูลไขมันโอเมกา 3 จากสถาบันสุขภาพแห่งชาติสหรัฐฯ', 'https://ods.od.nih.gov/factsheets/Omega3FattyAcids-Consumer/'),
    ('แนวทางอาหารสมดุลจากศูนย์ควบคุมและป้องกันโรคสหรัฐฯ', 'https://www.cdc.gov/nutrition/features/healthy-eating-tips.html'),
)

SKINCARE_GUIDANCE = {
    'acne': {
        'title_th': 'คำแนะนำเบื้องต้นสำหรับผิวที่มีลักษณะคล้ายสิว',
        'description': 'ระบบตรวจพบลักษณะภาพที่สอดคล้องกับสิว อย่างไรก็ตาม ผลตรวจไม่สามารถยืนยันชนิดหรือความรุนแรงของสิวได้',
        'daily_care': (
            'ล้างหน้าด้วยผลิตภัณฑ์อ่อนโยนตามปกติไม่เกินวันละ 2 ครั้ง และทำความสะอาดหลังเหงื่อออกมาก โดยไม่ขัดถูแรง',
            'หลีกเลี่ยงการแกะหรือบีบสิว เลือกผลิตภัณฑ์ที่ระบุว่า Non-comedogenic หรือไม่อุดตันรูขุมขน',
            'ใช้มอยส์เจอไรเซอร์ที่เหมาะกับผิวแม้มีผิวมัน และครีมกันแดด Broad-spectrum SPF 30 ขึ้นไป',
        ),
        'skincare_ingredients': (
            'Salicylic Acid (BHA): อาจช่วยดูแลรูขุมขนอุดตันและสิวบางประเภท',
            'Benzoyl Peroxide: เป็นสารในผลิตภัณฑ์รักษาสิวบางชนิด ไม่ได้หมายความว่าเหมาะกับทุกคน',
            'Moisturizer: ช่วยดูแลความชุ่มชื้นและลดความแห้งจากผลิตภัณฑ์รักษาสิว',
        ),
        'nutrition': (
            'รับประทานอาหารหลากหลาย เน้นผัก ผลไม้ ธัญพืชไม่ขัดสี และโปรตีนที่เหมาะสม',
            'หากดื่มเครื่องดื่มหวานหรือกินอาหารที่ทำให้น้ำตาลในเลือดเพิ่มเร็วเป็นประจำ อาจพิจารณาลดเพื่ออาหารที่สมดุลขึ้น',
            'หลักฐานด้านอาหารกับสิวยังมีข้อจำกัด ไม่ได้หมายความว่าอาหารชนิดหนึ่งเป็นสาเหตุในทุกคน หรือการปรับอาหารเพียงอย่างเดียวรักษาสิวได้',
        ),
        'exercise_lifestyle': ('ออกกำลังกายตามความเหมาะสม ใช้ผ้าสะอาดซับเหงื่อเบา ๆ และทำความสะอาดผิวอย่างอ่อนโยนหลังออกกำลังกาย', 'พักผ่อนให้เพียงพอ'),
        'cautions': ('ผลิตภัณฑ์รักษาสิวอาจทำให้แห้งหรือระคายเคือง ควรอ่านฉลากและปรึกษาเภสัชกรหรือแพทย์เมื่อไม่แน่ใจ', 'ผล AI ไม่สามารถเลือกความเข้มข้น ขนาดยา หรือระยะเวลารักษาให้บุคคลใดได้'),
        'when_to_seek_professional_care': ('สิวอักเสบมาก เจ็บลึก มีแผล เริ่มมีรอยแผลเป็น หรือไม่ดีขึ้นหลังดูแลอย่างเหมาะสม ควรปรึกษาแพทย์ผิวหนัง',),
        'references': (
            ('การดูแลผิวที่เป็นสิวจากสมาคมแพทย์ผิวหนังสหรัฐฯ', AAD+'diseases/acne/skin-care/tips'),
            ('อาหารกับสิวและข้อจำกัดของหลักฐาน', AAD+'diseases/acne/causes/diet'),
            ('ข้อมูลสารที่ใช้ดูแลสิว', AAD+'diseases/acne/derm-treat/treat/'),
            ('มอยส์เจอไรเซอร์สำหรับผิวที่เป็นสิว', AAD+'diseases/acne/skin-care/moisturizer'),
        ),
    },
    'wrinkle': {
        'title_th': 'คำแนะนำเบื้องต้นสำหรับผิวที่มีลักษณะคล้ายริ้วรอย',
        'description': 'ระบบพบลักษณะภาพคล้ายริ้วรอย แต่ไม่สามารถบอกความลึก อายุผิว หรือสาเหตุจากภาพนี้ได้',
        'daily_care': ('ใช้ครีมกันแดด Broad-spectrum SPF 30 ขึ้นไปเป็นประจำ และใช้มอยส์เจอไรเซอร์', 'เลี่ยงการขัดถูแรง และเลือกผลิตภัณฑ์ที่ไม่ระคายเคือง'),
        'skincare_ingredients': ('Moisturizer: อาจช่วยให้เส้นเล็ก ๆ จากผิวแห้งดูจางลงชั่วคราว ไม่ได้ลบริ้วรอยทั้งหมด', 'Retinol / Retinoids: อาจช่วยเรื่องริ้วรอยบางประเภท แต่มีข้อจำกัดและเสี่ยงระคายเคือง ควรปรึกษาผู้เชี่ยวชาญก่อนใช้'),
        'nutrition': ('รับประทานโปรตีนอย่างเหมาะสม และผักผลไม้หลายสี เช่น ฝรั่ง ส้ม และพริกหวาน', 'วิตามินซีมีบทบาทในการสร้างคอลลาเจนตามปกติ แต่ผลตรวจนี้ไม่ได้บอกว่าผู้ใช้ขาดวิตามินซี'),
        'exercise_lifestyle': ('หลีกเลี่ยงการสูบบุหรี่และการสัมผัสแดดมากเกินไป', 'ออกกำลังกายตามความเหมาะสมและพักผ่อนให้เพียงพอ เพื่อสุขภาพทั่วไป'),
        'cautions': (RETINOID_CAUTION, 'ครีมหรือ Retinol ไม่สามารถรับประกันว่าจะลบริ้วรอยทั้งหมดได้ หากแสบหรือระคายเคืองควรหยุดใช้'),
        'when_to_seek_professional_care': ('หากมีอาการแสบ แดง คันต่อเนื่อง หรือกังวลเรื่องการเปลี่ยนแปลงของผิว ควรปรึกษาแพทย์ผิวหนัง',),
        'references': (('การดูแลริ้วรอยจากสมาคมแพทย์ผิวหนังสหรัฐฯ', AAD+'everyday-care/skin-care-secrets/anti-aging/wrinkle-remedies'), RETINOID_REFERENCE, PREGNANCY_REFERENCE),
    },
    'dark_spot': {
        'title_th': 'คำแนะนำเบื้องต้นสำหรับผิวที่มีลักษณะคล้ายจุดด่างดำ',
        'description': 'ระบบพบจุดหรือบริเวณสีเข้มตามรูปแบบที่โมเดลเรียนรู้ ไม่สามารถระบุสาเหตุหรือยืนยันว่าเป็นรอยดำธรรมดาได้',
        'daily_care': ('ป้องกันแดด ใช้ครีมกันแดด Broad-spectrum SPF 30 ขึ้นไป และอาจพิจารณาชนิดมีสีที่มี Iron Oxide สำหรับรอยคล้ำบางประเภท', 'หลีกเลี่ยงการแกะสิวและขัดผิวแรง เลือกผลิตภัณฑ์อ่อนโยนเพื่อลดการระคายเคือง'),
        'skincare_ingredients': ('Azelaic Acid: เป็นหนึ่งในสารที่ใช้ดูแลรอยดำบางประเภท', 'Vitamin C ในผลิตภัณฑ์ดูแลผิว: อาจช่วยเรื่องสีผิวไม่สม่ำเสมอ ไม่รับประกันผลและอาจไม่เหมาะกับทุกคน'),
        'nutrition': ('รับประทานผักผลไม้หลากหลาย และอาหารให้เพียงพอต่อความต้องการทั่วไป', 'ไม่มีการรับรองว่าอาหารหรือวิตามินชนิดใดรักษารอยดำได้แน่นอน'),
        'exercise_lifestyle': ('หลีกเลี่ยงแดดจัด สวมหมวกหรือใช้อุปกรณ์ป้องกันแดด รวมถึงเมื่อออกกำลังกายกลางแจ้ง', 'ดูแลผิวอย่างอ่อนโยนหลังเกิดการระคายเคือง'),
        'cautions': ('ไม่ใช่ทุกจุดสีเข้มเป็นรอยดำธรรมดา อย่าใช้ผล AI วินิจฉัยฝ้า มะเร็งผิวหนัง หรือโรคอื่น', 'หลีกเลี่ยงครีมที่ไม่ทราบส่วนผสมหรือมีสารอันตราย'),
        'when_to_seek_professional_care': ('หากจุดสีเข้มเปลี่ยนรูปร่าง สี ขนาด หรือมีเลือดออก ควรให้แพทย์ผิวหนังประเมิน แทนการเชื่อผล AI แม้ระบบไม่ตรวจพบก็ตาม',),
        'references': (('การดูแลจุดด่างดำจากสมาคมแพทย์ผิวหนังสหรัฐฯ', AAD+'everyday-care/skin-care-secrets/routine/fade-dark-spots'), ('สัญญาณการเปลี่ยนแปลงของจุดบนผิวที่ควรตรวจ', AAD+'diseases/skin-cancer/abcdes-melanoma')),
    },
    'enlarged_pore': {
        'title_th': 'คำแนะนำเบื้องต้นสำหรับผิวที่มีลักษณะคล้ายรูขุมขนกว้าง',
        'description': 'ระบบพบลักษณะภาพคล้ายรูขุมขนกว้าง ไม่สามารถยืนยันสภาพผิว สาเหตุ หรือความผิดปกติจากจำนวนกรอบที่พบได้',
        'daily_care': ('ล้างหน้าอย่างอ่อนโยน ไม่ขัดถูรุนแรง เลือกผลิตภัณฑ์ Non-comedogenic และล้างเครื่องสำอางก่อนนอน', 'ใช้ครีมกันแดด Broad-spectrum SPF 30 ขึ้นไป'),
        'skincare_ingredients': ('Salicylic Acid: อาจช่วยดูแลรูขุมขนที่มีการอุดตัน', 'Retinol: อาจช่วยให้รูขุมขนดูเด่นน้อยลงในบางกรณี แต่มีข้อจำกัดและอาจระคายเคือง ควรปรึกษาผู้เชี่ยวชาญก่อนใช้'),
        'nutrition': ('รับประทานอาหารครบหมู่ เน้นผัก ผลไม้ และโปรตีนตามความเหมาะสม', 'ไม่ควรคาดหวังว่าอาหารชนิดใดทำให้รูขุมขนหดเล็กลงโดยตรง'),
        'exercise_lifestyle': ('ทำความสะอาดผิวหลังเหงื่อออก ใช้เครื่องสำอางที่ไม่อุดตันรูขุมขน', 'หลีกเลี่ยงการสัมผัสหน้าด้วยมือที่ไม่สะอาด'),
        'cautions': (RETINOID_CAUTION, 'การดูแลอาจทำให้รูขุมขนดูเด่นน้อยลง แต่ไม่สามารถปิดรูขุมขนได้ถาวร'),
        'when_to_seek_professional_care': ('หากมีการอักเสบ เจ็บ ระคายเคืองต่อเนื่อง หรือไม่แน่ใจว่าเป็นรูขุมขน ควรปรึกษาแพทย์ผิวหนัง',),
        'references': (('การดูแลรูขุมขนจากสมาคมแพทย์ผิวหนังสหรัฐฯ', AAD+'everyday-care/skin-care-secrets/face/treat-large-pores'), PREGNANCY_REFERENCE),
    },
}


def detected_classes(counts):
    """Canonical order, positive finite counts only; ignore unknown names, never remap IDs.

    Counts select educational topics, not severity, dosage, diagnosis or nutrition status.
    """
    if not isinstance(counts, Mapping):
        return ()
    return tuple(name for name in CLASSES if isinstance(counts.get(name), Real)
                 and not isinstance(counts[name], bool) and math.isfinite(counts[name]) and counts[name] > 0)


def guidance_topics(counts, *, showcase=False):
    """An explicit showcase shows labelled static examples, never invented detections."""
    return tuple(CLASSES) if showcase else detected_classes(counts)
