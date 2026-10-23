# Licensing gate — LICENSE_UNVERIFIED

ตรวจจากแหล่งทางการวันที่ 2026-10-23 ไม่มีการติดต่อผู้ให้บริการหรือขออนุญาตแทนผู้ใช้ ไม่มีการโหลด Model package เพิ่ม

| ส่วน | หลักฐาน | สิ่งที่ยืนยันได้ / ข้อจำกัด |
|---|---|---|
| Dataset | [SKN-1 Universe](https://universe.roboflow.com/skn-f1vaw/skn-1) | หน้า Project ระบุ CC BY4.0 ไม่ใช่หลักฐานสิทธิ์ Weights/Remote service |
| Architecture/code | [Roboflow YOLO-NAS documentation](https://inference-models.roboflow.com/models/yolonas-object-detection/) และ [SuperGradients code license](https://github.com/Deci-AI/super-gradients/blob/master/LICENSE.md) | Code Apache2.0; Architecture name หรือ Code license ไม่ได้ให้สิทธิ์ Weights โดยอัตโนมัติ |
| Deci pre-trained weights | [LICENSE.YOLONAS.md](https://github.com/Deci-AI/super-gradients/blob/master/LICENSE.YOLONAS.md) | มีข้อจำกัด Distribution/Remote access/Managed services โดยไม่มี Written consent และเงื่อนไข Commercial use |
| Roboflow provenance | [SKN-1 Universe](https://universe.roboflow.com/skn-f1vaw/skn-1) | skn-1/2 เป็น YOLO-NAS, Checkpoint coco/14 ตามหน้า Model; ยังไม่ยืนยันสิทธิ์ต่อเนื่องของ Weights ชุดที่ SDK ส่งมา |
| Self-hosted remote inference | ยังไม่มีสิทธิ์เฉพาะ skn-1/2 หรือ Written permission | LICENSE_UNVERIFIED แม้เป็น Non-commercial/Private URL ส่งอาจารย์ |

Official Roboflow docs แยก Code license กับ Deci pre-trained weights license โดยตรง จึงไม่อนุมานสิทธิ์ Weights จาก CC BY4.0 บนหน้า Dataset หรือจากการที่ SDK ดาวน์โหลดได้

เอกสาร Roboflow ยังระบุว่าโมเดลที่ฝึกด้วย Roboflow Train อนุญาต Commercial usage เพราะไม่ใช้ Deci weights อย่างไรก็ตาม ยังไม่มีหลักฐานว่า skn-1/2 ชุดนี้เข้าเงื่อนไขนั้นอย่างไร และหน้า Model ระบุ checkpoint coco/14 จึงต้องให้ผู้ให้บริการยืนยัน Provenance/เงื่อนไขของรุ่นนี้โดยเฉพาะ ไม่สรุปว่าใช้ Deci weights หรือได้รับข้อยกเว้นโดยอัตโนมัติ

## Gate ก่อนเปิดบริการ

- [ ] ผู้ให้บริการยืนยันเจ้าของและ License ของ Weights skn-1/2 ที่ใช้จริง
- [ ] ยืนยันที่มาของ Base checkpoint และเงื่อนไขที่ส่งต่อมายัง Weights รุ่นนี้
- [ ] ยืนยันสิทธิ์ Server-side execution บน Streamlit Community Cloud และการให้บุคคลอื่นใช้ผ่าน URL
- [ ] แยก Public/Private access, Non-commercial educational use, Distribution และ Attribution requirements ให้ชัด
- [ ] เก็บหลักฐานสิทธิ์ในพื้นที่ผู้ใช้ควบคุม ไม่ Commit อีเมลส่วนบุคคล/เอกสารลับโดยอัตโนมัติ
- [ ] ผ่าน Cloud runtime tests ตามคู่มือ โดยยังไม่มี Media ถูกส่งไป Remote inference API

Source-only CI ไม่ดาวน์โหลด/ใช้/แจก Weights และไม่เปิดบริการอนุมาน จึงเตรียม CI ต่อได้โดยยังคง Gate นี้ไว้ ผล CI ไม่ใช่ Legal clearance ไม่มีการประกาศว่า Source repository ทั้งหมดใช้ CC BY หรือ Apache โดยอัตโนมัติ
