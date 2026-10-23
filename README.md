# SKN-1 Streamlit Deployment / Linux CI

สำเนา Source-only ของแอปเดียวกับ ML-Assignment แยก Git history จาก Research repository ไม่รวม Dataset, Weights, Cache หรือภาพใบหน้า

**สถานะเริ่มต้น: LINUX_BUILD_PENDING_CI / LICENSE_UNVERIFIED** ยังไม่มีแอปออนไลน์ ห้ามเปิด Model inference service จนยืนยันสิทธิ์ของ skn-1/2 และ Cloud runtime จริง

- Entrypoint: `deployment/streamlit_app.py`
- Python: 3.11
- Dependencies: `deployment/requirements.txt`; Linux libraries: `packages.txt`
- Exact initial commit allowlist: `ci/audit_source.py:FILES` (รวม `bundle_manifest.json`)
- Fingerprints: `bundle_manifest.json`; Provenance จาก Research bundle: `SOURCE_PROVENANCE.json`
- คู่มือ Cloud: [DEPLOY_STREAMLIT_CLOUD.md](DEPLOY_STREAMLIT_CLOUD.md)
- สิทธิ์โมเดล: [docs/LICENSING.md](docs/LICENSING.md)
- ร่างขออนุญาตที่ยังไม่ส่ง: [docs/LICENSE_PERMISSION_REQUEST.md](docs/LICENSE_PERMISSION_REQUEST.md)

## Linux CI ที่เตรียมไว้

หลังผู้ใช้อนุมัติ Commit/Push ไป main Workflow `Linux source-only build` จะใช้ Ubuntu22.04/Python3.11 ติดตั้ง packages.txt และ requirements เดิม → pip check → ตรวจ Imports/CPU provider/libvips/H.264 → Synthetic tests → Render initial Streamlit UI/Localhost health → ตรวจ Source/Temp อีกครั้ง ไม่มีการ Deploy

CI ไม่ใช้ Roboflow key, ไม่ดาวน์โหลด Weights, ไม่เรียก Model constructor/Remote inference และไม่ใช้ภาพจริง Dependencies ดาวน์โหลดจาก Public indexes ได้เฉพาะ Installation phase ส่วน Capability/Synthetic/Startup checks บล็อก Network ยกเว้น Loopback Synthetic suite บล็อกการ Import SDK จริงอีกชั้นและใช้ Fake runtime เท่านั้น

ไม่ Upload Build artifacts หรือ Dependency caches ไม่มี GitHub Secrets references Actions pin ด้วย SHA ที่ตรวจจาก Repository ทางการ และตั้ง contents:read/persist-credentials:false

`pip check` หรือ Imports อาจล้มเหลวจาก SDK mandatory dependencies ที่ยังไม่ผ่าน Linux resolution ห้ามสรุปว่า Build ผ่านจาก Windows tests และห้ามแก้ด้วย --no-deps หรือเปลี่ยน Package versions โดยไม่มีหลักฐาน

## คำสั่งใน Deployment-only directory

คำสั่งนี้ใช้ Environment ที่มี Dependencies อยู่แล้ว ไม่ติดตั้งอะไรบนเครื่องผู้ใช้โดยอัตโนมัติ:

```text
python -B -m ci.audit_source
python -B -m ci.run_synthetic
python -B -m ci.startup_smoke
# ci.check_runtime ใช้ใน Linux environment ที่ติดตั้ง Cloud requirements ครบแล้วเท่านั้น
```

หากแก้ Source ให้ผู้ดูแลตรวจ Exact allowlist แล้วคำนวณ SHA256 ใหม่สำหรับทุกไฟล์ใน FILES ยกเว้นตัว Manifest เอง ก่อน Commit ห้ามเพิ่มไฟล์ด้วย Glob หรือ Copy ทั้ง Research repository

`reports/` เป็น Verification metadata เฉพาะเครื่อง ไม่อยู่ใน Commit allowlist `.ci_tmp/` ใช้ Synthetic fixtures เท่านั้น ไม่เผยแพร่ทั้งสองพื้นที่ ห้ามใช้ Reports จาก Research project เป็น Build artifacts

GitHub Actions success ยืนยัน Linux source/build/capabilities ตามที่ทดสอบ ไม่ยืนยัน Model access, Cloud Model loading, Image/Video inference หรือสิทธิ์เผยแพร่ ต้องตรวจแยกภายหลัง
