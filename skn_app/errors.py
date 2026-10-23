"""Only fixed codes/messages cross process or UI boundaries."""
MESSAGES = {
    'AUTH_MISSING': 'ยังไม่พร้อมตรวจจับ: ผู้ดูแลต้องตั้งค่า ROBOFLOW_API_KEY',
    'MODEL_NOT_READY': 'ยังไม่พร้อมตรวจจับ: โหลด Model package ไม่สำเร็จ กรุณาให้ผู้ดูแลตรวจ Runtime และสิทธิ์เข้าถึง',
    'LOCAL_ENV_MISSING': 'ไม่พบ SKN Python Environment สำหรับ Local กรุณาตรวจคู่มือติดตั้ง',
    'LOCAL_CACHE_INVALID': 'Local model cache ไม่ครบหรือไม่ผ่านการตรวจ Identity',
    'RESOURCE_LIMITED': 'ทรัพยากรหน่วยความจำไม่เพียงพอสำหรับงานนี้ กรุณาลองเมื่อมีทรัพยากรพร้อม',
    'RESOURCE_UNKNOWN': 'ตรวจงบหน่วยความจำไม่ได้ จึงยังไม่เริ่ม Inference',
    'BUSY': 'มีงานกำลังประมวลผลอยู่ กรุณารอแล้วลองใหม่',
    'IMAGE_INVALID': 'ไฟล์ต้องเป็นภาพ JPG/JPEG/PNG ที่อ่านได้',
    'UPLOAD_TOO_LARGE': 'ไฟล์มีขนาดเกินข้อจำกัดของ Demo',
    'IMAGE_DIMENSIONS': 'ภาพมีจำนวนพิกเซลมากเกินไป กรุณาลดขนาดภาพ',
    'VIDEO_INVALID': 'อ่านไฟล์ MP4 หรือ Metadata ไม่สำเร็จ',
    'VIDEO_LIMITS': 'วิดีโอต้องยาวไม่เกิน 12 วินาที และไม่เกิน 1280 พิกเซลด้านยาว / 1280×720 พิกเซลรวม',
    'VIDEO_ROTATION': 'วิดีโอมี Rotation metadata ที่ยังไม่รองรับ กรุณา Export เป็นภาพตั้งตรงก่อนอัปโหลด',
    'VIDEO_CODEC': 'Runtime นี้ยังไม่มี Codec สำหรับอ่านหรือ Export H.264 จึงไม่พร้อมตรวจวิดีโอ',
    'VIDEO_IMAGE_FIRST': 'กรุณาทดสอบ Image Detection ให้สำเร็จใน Session นี้ก่อนเปิด Video บน Cloud',
    'JOB_TIMEOUT': 'งานใช้เวลาเกินขีดจำกัดและถูกหยุด กรุณาลดขนาดหรือระยะเวลาวิดีโอ',
    'INPUT_INVALID': 'ข้อมูลหรือผลลัพธ์ของงานไม่ผ่านการตรวจสอบ',
    'INFERENCE_FAILED': 'Inference ไม่สำเร็จ ไม่มีผลทำนายสำหรับงานนี้ กรุณาให้ผู้ดูแลตรวจ Runtime',
}


class AppError(Exception):
    def __init__(self, code):
        self.code = code if code in MESSAGES else 'INFERENCE_FAILED'
        super().__init__()


def safe_code(error):
    return error.code if type(error) is AppError and error.code in MESSAGES else 'INFERENCE_FAILED'
