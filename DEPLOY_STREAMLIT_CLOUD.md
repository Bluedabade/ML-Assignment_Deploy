# Deploy SKN-1 Image / Offline Video Demo บน Streamlit Community Cloud

## Deployment-only repository นี้

สถานะ **LINUX_BUILD_PENDING_CI / LICENSE_UNVERIFIED / CLOUD_UNVERIFIED** Repository นี้คือ `Bluedabade/ML-Assignment_Deploy` มีประวัติ Git ใหม่ ไม่มี Dataset, Weights, Research history หรือ Windows environments คู่มือส่วน Local ด้านล่างใช้กับ **Full Research Project เท่านั้น**

Entrypoint ของ Repository นี้คือ `deployment/streamlit_app.py` และใช้ `deployment/requirements.txt` ไม่ใช่ Root training requirements บน Linux เลือก Cloud mode อัตโนมัติ อย่าตั้ง SKN_APP_MODE=local บน Cloud

Exporter ใช้เฉพาะใน Research project จึงไม่รวมใน Deployment repository การดูแลชุดนี้ใช้ Exact allowlist ที่ `ci/audit_source.py:FILES` และ SHA256 ใน `bundle_manifest.json` แทน ไม่ Copy Tools/Cache helpers จาก Research project เพื่อให้คำสั่ง Local ทำงาน

อ่าน [README](README.md) สำหรับ CI และ [Licensing gate](docs/LICENSING.md) ก่อนเผยแพร่ ร่างขอยืนยันสิทธิ์อยู่ [ที่นี่](docs/LICENSE_PERMISSION_REQUEST.md) และยังไม่ได้ส่ง

## สถานะและเงื่อนไขก่อนเผยแพร่

เอกสารนี้เป็นขั้นเตรียม Deployment ไม่ใช่หลักฐานว่ามีแอปออนไลน์แล้ว ห้ามเรียก LIVE VERIFIED จนทดสอบ URL จริง ภาพ และวิดีโอบน Community Cloud สำเร็จ

**ยังไม่อนุมัติการเผยแพร่:** ต้องตรวจสิทธิ์ Model weights และผ่าน Linux build/runtime ก่อน หน้า [SKN-1 Universe](https://universe.roboflow.com/skn-f1vaw/skn-1) ระบุ CC BY4.0 แต่ไม่เพียงพอยืนยันสิทธิ์ให้บริการ Weights ผ่านเว็บ [YOLO-NAS weights license ของ Deci](https://github.com/Deci-AI/super-gradients/blob/master/LICENSE.YOLONAS.md) มีข้อจำกัดเรื่อง Remote access/Managed services และ Commercial use ต้องให้เจ้าของสิทธิ์หรือผู้เกี่ยวข้องยืนยันเงื่อนไขของ skn-1/2 ที่ใช้จริงก่อน Publish แม้เป็น Private URL สำหรับส่งงานก็ต้องตรวจเรื่องนี้ ไม่อัปโหลด Weights ไป GitHub/Storage อื่นเอง

## Architecture ที่ใช้ร่วมกัน — Local หมายถึง Full Research Project

- Local entrypoint: `streamlit_app.py`; ใช้ Streamlit Environment เดิม และ Persistent worker ใน SKN Environment เดิม
- Cloud entrypoint: `deployment/streamlit_app.py`; เป็น Wrapper เรียก `skn_app.ui.main` เดียวกัน ไม่ใช่แอปอีกชุด
- `skn_app/media.py` ประมวลผลไฟล์/เฟรมและ Export; `runtime.py` ใช้ Official SDK ONNX CPU
- Local discovery อยู่ใน `local_adapter.py` เท่านั้น ปรับ `SKN_PYTHON`/`SKN_LOCAL_MODEL_CACHE` ได้ ไม่มี D:\Projects ใน Shared modules
- Local คัดลอก Cache เดิมลง Temporary runtime แบบ Shared-blob symlinks พร้อมตรวจ Hash ไม่เขียน Cache ต้นฉบับ
- Cloud เริ่มด้วย Cache ว่างใน Temporary storage แล้วให้ SDK โหลด `skn-1/2` ผ่าน Authentication ตามปกติ ตรวจ CPU provider/Class mapping/Weights fingerprint ไม่อาศัย Windows cache หรือ Persistent disk
- โมเดลโหลดแบบ Lazy และเก็บด้วย `st.cache_resource` เฉพาะ Resource ไม่ Cache Uploaded media ผลทำนายอยู่ใน Session เท่านั้น มีหนึ่ง Inference job ต่อ App process
- คง NMS0.30, raw cap300, full-image detection, Original model preprocessing และ Security flags False ทั้งสองค่า

## ข้อจำกัด Demo

| รายการ | ข้อจำกัด |
|---|---|
| ภาพ | JPG/JPEG/PNG, <=5MiB, <=4,194,304 pixels, ด้านยาว<=4096 |
| วิดีโอ | MP4, <=20MiB, <=12วินาที, ด้านยาว<=1280, พิกเซลรวม<=1280×720, FPSต้นทาง<=60 |
| การตรวจวิดีโอ | 1เฟรม/วินาที, <=12เฟรม, ไม่ใช่ Real-time, ไม่ตรวจทุกเฟรม |
| Export | Annotated PNG, CSV, Sampled-frame MP4 H.264/yuv420p ไม่มีเสียง |
| Rotation | ปฏิเสธ Rotation/display-matrix metadata ที่ยังไม่รองรับ ให้ Export ไฟล์ตั้งตรงก่อน |
| Profiles | Balanced=.25 ทุกคลาส; Precision-focused=.25/.45/.275/.30 ตาม acne/wrinkle/dark_spot/enlarged_pore |

Precision-focused มี Recall tradeoff โดยเฉพาะ wrinkle ไม่ใช่ Confidence calibration หรือการวินิจฉัยโรค ไม่พบ Detection ไม่ได้หมายถึงผิวปกติ

## Dependencies และ Linux compatibility

`requirements.txt` ที่ Root เดิมเป็นชุด Training ให้รักษาไว้ Cloud ต้องเลือก Entrypoint `deployment/streamlit_app.py` เพื่อให้ [Requirements ข้าง Entrypoint มีลำดับก่อน Root](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)

`deployment/requirements.txt` เป็น Candidate สำหรับ Python3.11 มี Streamlit1.65.0, Official inference-models[onnx-cpu]0.39.1, CPU-only Torch2.14.1/torchvision0.29.1, ORT1.22.1 และ PyAV18.1.0 ไม่เพิ่ม ultralytics, super-gradients, Jupyter หรือ Dataset ของโปรเจกต์

**ข้อค้าง:** SDK0.39.1 มี Mandatory dependencies ของ Model zoo เช่น peft/bitsandbytes/pycocotools ซึ่งแอป SKN ไม่ได้เรียกโดยตรง แต่ Pip จะดึงตาม SDK Metadata จึงยังอ้างว่าเป็น Minimal inference-only dependency closure ไม่ได้ ไม่ใช้ `--no-deps` หรือแก้ SDK metadata เพื่อหลบข้อกำหนด

ตรวจ Public Linux wheels ของ Direct packages และ CPU wheels แล้ว แต่ Binary-only cross-platform dry-run หยุดที่ pyvips ซึ่งต้องใช้ Source build/Native library จึงยังไม่ใช่ CLOUD_DEPENDENCIES_VERIFIED การทดสอบ WSL Ubuntu เดิมเริ่มไม่ได้ด้วย Wsl/Service/CreateInstance/E_UNEXPECTED ไม่ได้ติดตั้งหรือซ่อมระบบ

`packages.txt` ที่ Root เตรียม libgl1/libglib2.0-0 สำหรับ SDK opencv-python, libvips42 สำหรับ pyvips และ libcairo2 สำหรับ CairoSVG ที่ SDK ดึงมา ห้ามถือว่า Build ผ่านจนเห็น Cloud build สำเร็จจริง [Debian package reference](https://packages.debian.org/search?keywords=libvips42)

ใช้ PyAV wheel ที่มี H.264 encoder แทนการเรียก ffmpeg executable ทดสอบ Local แล้ว แต่ Linux codec ยังต้องตรวจจริงก่อนยืนยัน Cloud Video [Streamlit แนะนำ H.264 เพื่อ Browser playback](https://docs.streamlit.io/1.65.0/develop/api-reference/media/st.video)

## Memory และ Concurrency

ผู้ใช้อนุญาตให้ปิด Application RAM admission guard สำหรับ Cloud demo แล้ว ไม่มีการปฏิเสธงานจากเกณฑ์768/128/192MiBเดิม ฟังก์ชันยังอ่าน Host/cgroup telemetry โดยไม่แก้ระบบ ขีดจำกัด cgroup ของ Hosting ยังบังคับใช้และอาจทำให้ Process ถูกปิดหากใช้เกิน ไม่ถือว่าการปิด Guard เป็นการเพิ่ม RAM หรือรับรองว่าจะไม่ OOM

Concurrent job ที่สองได้รับ BUSY ไม่มี Queue ของ Workers จำนวนมาก Cloud Video ต้องผ่าน Image inference จริงใน Session ก่อน คง Upload/Video/เวลาและDetection caps เดิม Runtime/Memory expander แสดงข้อมูลตัวเลขที่ไม่มีSecretsเพื่อทดสอบ Cloud จริงก่อนส่งงาน ไม่ติดตั้ง Package หรือส่ง Media ไป Remote inference API เพื่อหลบข้อจำกัด

## Secret configuration

Local ใช้ Project-root `.env` เดิม Process environment มีลำดับก่อน แม้ค่าที่ตั้งไว้จะว่าง จึงไม่ถูก Secrets/dotenv เขียนทับ Cloud ใช้ Process environment ก่อน `st.secrets` และไม่อ่าน Local `.env`

ใน Community Cloud Advanced settings / Secrets ใส่เฉพาะ:

```toml
ROBOFLOW_API_KEY = "REPLACE_WITH_PRIVATE_KEY"
```

ตัวอย่างอยู่ใน `deployment/secrets.example.toml` และ `deployment/.env.example` ห้าม Commit `.env` หรือ `.streamlit/secrets.toml` ห้ามใส่ Key ใน CLI, URL, Screenshot, Issue หรือ Logs ไม่ต้องใส่ Windows paths ใน Cloud

## เตรียม GitHub repository อย่างปลอดภัย

Repository งานเดิมติดตาม Dataset มากกว่า15,000ไฟล์ รวม Runs/Results อยู่แล้ว การเพิ่ม .gitignore ไม่ทำให้ไฟล์ที่ติดตามอยู่หายไป **อย่า Push Repository งานทั้งชุดเพียงเพื่อ Deploy**

คำสั่งต่อไปนี้ใช้เฉพาะจาก **Full Research Project** เท่านั้น ไม่รันจาก Deployment repository ซึ่งไม่มี Exporter:

```powershell
python deployment/export_bundle.py <absolute-new-empty-destination>
```

Destination ต้องยังไม่มีอยู่และ Parent ต้องมีอยู่แล้ว Bundle มีเฉพาะ `skn_app/`, Entrypoints, Cloud requirements, packages/config, Template secrets และคู่มือ ไม่มี Dataset, Checkpoints, Cache, Evaluation artifacts, Uploaded media หรือ Credentials

ใช้ Bundle เป็นเนื้อหาของ Repository/Deploy branch ที่ผู้ใช้ตรวจแล้ว เป็น Deployment copy ของแอปเดียว ไม่ใช่แอปแยกสำหรับพัฒนา ขั้น Commit/Push ให้ผู้ใช้อนุมัติและดำเนินการภายหลัง ไม่ใช้ `git add .` จากโปรเจกต์งานเดิม และไม่ Reset/Clean/Untrack Dataset เพื่อเตรียม Cloud

### Checklist ก่อน Commit/Push โดยผู้ใช้

- [ ] ตรวจ `bundle_manifest.json` และรายการไฟล์ทุกไฟล์
- [ ] ไม่มี .env/.streamlit/secrets.toml, *.pt, *.onnx, model_cache, datasets, runs, results หรือ Media
- [ ] ไม่รวม Workbench/Optimization local changes ที่ไม่เกี่ยวข้อง
- [ ] Root training requirements เดิมไม่ได้ถูกแก้หรือใช้เป็น Cloud requirements
- [ ] ตรวจสิทธิ์ Model weights สำหรับ Remote access แล้วและเก็บหลักฐานไว้
- [ ] ทดสอบ Linux install/build โดยไม่ข้าม Dependencies หรือผ่อน Security flags
- [ ] ผู้ใช้อนุมัติ Source diff และ Commit/Push แล้ว

## เผยแพร่ Community Cloud ทีละขั้น

1. สมัคร/เข้าสู่ระบบ [Streamlit Community Cloud](https://share.streamlit.io/) เชื่อม GitHub ตามสิทธิ์ที่จำเป็น
2. เตรียม Repository ที่มี Source-only bundle หลังผ่าน Checklist ไม่อัปโหลด Model cache จาก Windows
3. Create app → เลือก Repository, Branch และ Entrypoint **`deployment/streamlit_app.py`**
4. Advanced settings → เลือก **Python3.11** อย่าใช้ Default โดยไม่ตรวจ (SDK0.39.1 รองรับ Python>=3.10,<3.14)
5. ใส่ Secrets ด้วย Key จริงใน Cloud UI เท่านั้น เลือก Subdomain ที่ต้องการ แล้ว Deploy ด้วยตนเอง
6. ตรวจ Build logs เฉพาะผู้ดูแล อย่าคัดลอก Credential/Request URLs มารายงาน หาก Source/native build ล้มเหลวให้หยุด ไม่แก้ด้วย Security flags
7. เปิด App → อัปโหลดภาพที่ได้รับอนุญาต → ตรวจจับ การโหลดครั้งแรกอาจติดต่อ Roboflow เพื่อ Package metadata/artifacts ภาพส่งเข้า ONNX ใน App runtime ไม่ใช่ Remote image API
8. ยืนยัน Model load และ Image result จริงก่อนวิดีโอ ตรวจ Bounding boxes,4คลาส, Empty-detection wording และดาวน์โหลด PNG/CSV
9. ทดสอบ MP4สั้น2วินาทีก่อน ตรวจ Progress, timestamps0/1, Sampled-frame H.264 playback ใน Browser และดาวน์โหลด MP4/CSV
10. หาก Memory/Time/Codec ไม่พร้อม ให้รายงาน Cloud Video resource-limited/unsupported ห้ามเรียกว่า Cloud Video verified จาก Local test
11. ตั้ง Public/Private ใน App sharing ตามสิทธิ์และความเหมาะสม ทดสอบจาก Browser/บัญชีอาจารย์จริง ไม่อนุมาน Visibility จาก Repository visibility เพียงอย่างเดียว [Sharing docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)
12. ส่ง URL ให้อาจารย์หลังผ่าน Smoke tests และ Access test พร้อมแจ้งข้อจำกัด File size/Duration/1FPS และใช้ Media ที่ได้รับอนุญาต

ขั้น UI/Python/Secrets อ้างอิง [Official deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) ชื่อเมนูอาจเปลี่ยน ให้ตรวจใน Cloud UI จริง

## Acceptance evidence ที่ต้องเก็บ

| สถานะ | หลักฐานที่จำเป็น |
|---|---|
| LOCAL_IMAGE_VERIFIED | SKNจริงรับภาพได้ / Bounding boxesหรือผลว่างจริง / Export PNG/CSV |
| LOCAL_VIDEO_VERIFIED | SKNจริงตรวจ Sampled frames / timestamps / MP4 H.264เปิดในBrowser / CSV |
| CLOUD_DEPENDENCIES_VERIFIED | Linux Python3.11 build/installสำเร็จจริง ไม่ใช่เพียงมีWheel |
| CLOUD_MODEL_LOAD_VERIFIED | App Cloudโหลดskn-1/2จากไม่มีCache, CPU provider/weights identityถูกต้อง |
| CLOUD_IMAGE_INFERENCE_VERIFIED | Image upload/inference/exportผ่านบนCloudจริง |
| CLOUD_VIDEO_INFERENCE_VERIFIED | MP4/progress/export/browser playbackผ่านบนCloudภายในResource budget |
| PUBLIC_OR_PRIVATE_APP_ACCESS_VERIFIED | เปิดURLด้วยผู้ใช้เป้าหมายตามVisibilityจริง |

ยังไม่ Deploy หมายถึง Cloud runtime/access ทั้งหมดยัง UNVERIFIED ไม่ใช้ Mock/Synthetic unit results แทนการตรวจบน Cloudจริง

## Privacy และ Retention

- Job directories สุ่มแยกกันใน OS temp; Worker responses ผูก Job ID ไม่รับผลค้างจาก Session อื่น; ล้างเมื่อสำเร็จ/ผิดพลาด/ยกเลิกตามปกติ
- ไม่เก็บ Media ใน Repository/Benchmark และไม่ Cache Media globally ผล Downloads อยู่ใน Session memory จน Clear/Session expiry; TTL ตรวจเมื่อ Rerun ไม่ใช่ Secure deletion timer
- Model resource/cache เป็น App-level เท่านั้น ไม่ใส่ภาพลง Model cache
- ไม่เปิด Static serving ของ Job folders และไม่แสดง Private paths/Raw SDK errors
- ผลดาวน์โหลด/ลิงก์ Media ที่ Browser ได้รับถือเป็นข้อมูลส่วนตัว ไม่ควรส่งต่อ; Visibility ต้องตรวจบน Cloudจริง
- Process/OS crash อาจทำให้ Temp cleanup ไม่ทัน ต้องมี Host temp retention/ตรวจไฟล์ค้างก่อนใช้ข้อมูลอ่อนไหว ไม่รับรอง Secure erasure จาก Cloud provider
- ไม่ส่ง Media ไป Third-party inference API Model-package provisioning เป็น Network operation แยกต่างหาก

## Troubleshooting / Update / Rollback

- BuildเลือกRoot requirementsผิด: ตรวจ Entrypoint และไฟล์ข้าง Entrypoint ตามลำดับของCommunity Cloud
- pyvips/native library error: ตรวจ packages.txt/Build logsและLinux dependency closure อย่าลบDependenciesหรือบังคับ--no-depsเพื่อให้ผ่าน
- Auth/Package access: ตรวจSecretในCloud UI, Model IDและสิทธิ์ แล้ว Reboot App ไม่ Print Key/Raw exception
- Missing cache หลังRestart: เป็นพฤติกรรมที่รองรับ ให้SDKProvisionใหม่ ไม่คาดหวังPersistent disk
- Resource failure/OOM: ตรวจ Memory telemetry ลดขนาดMedia/จำนวนผู้ใช้หรือเปลี่ยนHostingตามการอนุมัติ Guard ของแอปปิดตามคำสั่งผู้ใช้แล้ว แต่ Platform memory limit ไม่ได้เพิ่ม
- วิดีโอเปิดไม่ได้: ตรวจ H.264/yuv420p จากExportจริง ไม่ใช้MP4Vแทนแล้วเรียกว่ารองรับBrowser
- อัปเดต: ตรวจDiff/Testsก่อนให้ผู้ใช้Commit/Push CloudจะRebuildเมื่อSource/Dependenciesเปลี่ยน ตรวจImageก่อนVideoซ้ำหลังDeployทุกครั้ง
- Rollback: จดCommitที่ผ่านและSettingsไว้ ให้ผู้ใช้สร้างRevert commitของApp changesบนDeploy repo ไม่ใช้Reset/Cleanกับโปรเจกต์งานเดิม แล้วทดสอบใหม่
- เปลี่ยนPython: [ต้องลบและRedeploy AppตามOfficial docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python) หลังจดRepo/Branch/Entrypoint/Subdomainและเก็บSecretsอย่างปลอดภัย ห้ามบันทึกSecretsในRollback notes

## Full Research Project เท่านั้น — Local launch และ Model Smoke tests

```powershell
.\run_streamlit.ps1
# หรือใช้ Existing Streamlit environment เปิด root streamlit_app.py บน127.0.0.1
& ..\ML-Assignment-roboflow-env\Scripts\python.exe -B -m unittest discover -s tests -p test_skn_app.py -v
& ..\ML-Assignment-roboflow-env\Scripts\python.exe -B tools/smoke_skn_app.py --output <new-private-check-directory>
```

Smoke script ไม่บันทึก Face image ที่ป้อนเข้า เก็บเฉพาะ Metrics metadata และ Synthetic face-free MP4 สำหรับทดสอบCodec Existing inference/evaluation scriptsไม่ได้ถูกเรียกจากCloud app

## Deployment-only Project — CI และ Smoke tests ที่ไม่ใช้โมเดล

ใช้ Environment ที่ติดตั้ง Dependencies อยู่แล้ว คำสั่งเหล่านี้ไม่ติดตั้ง Package หรือโหลด SKN-1:

```text
python -B -m ci.audit_source
python -B -m ci.run_synthetic
python -B -m ci.startup_smoke
```

`ci.check_runtime` ใช้ใน Linux Environment ที่ติดตั้ง Cloud requirements ครบ ตรวจ Imports, ONNX CPU provider, Native libvips operation และ H264 encoder ไม่มี Model constructor call Workflow `.github/workflows/linux-build.yml` ใช้ Ubuntu22.04/Python3.11 ติดตั้ง packages.txt/requirements เดิม และรัน pip check ก่อน Tests ไม่ใช้ API key/Secrets ไม่ Upload artifacts/caches และไม่ Deploy

Probe/Test phases บล็อก Network ยกเว้น Loopback และ Synthetic tests บล็อก SDK จริง ส่วน Installation phase ดาวน์โหลด Public packages ได้ตามปกติ Scratch ใช้ `.ci_tmp/` และ Local reports ใช้ `reports/` ทั้งสองพื้นที่ห้าม Commit ต้องตรวจ Source audit และ Manifest อีกครั้งหลังแก้ไฟล์

ตาม [pyvips official documentation](https://libvips.github.io/pyvips/README.html) CFFI ABI mode ใช้ libvips shared library ส่วน API mode ต้องใช้ Headers/Compiler จึงยังไม่เพิ่ม libvips-dev/build-essential โดยไม่มีข้อผิดพลาดที่ยืนยัน CI จะตรวจ `pyvips.Image.black`, Library version และ API_mode ก่อนพิจารณา Build dependencies เพิ่ม ไม่ใช้ --no-deps และไม่ลด Mandatory SDK dependencies

PyAV ใช้ libx264 ของ Wheel ไม่ต้องมี ffmpeg executable แต่ต้องผ่าน Native encoder/decoder test บน Linux จริง CI Ubuntu ไม่เหมือน Community Cloud Debian ทุกประการ ผล CI ผ่านไม่ยืนยัน Cloud Model load/Image/Video/Memory หรือ License ต้องตรวจแยกหลังผู้ใช้อนุมัติขั้นถัดไป


## หน้าจอภาษาไทยฉบับปรับปรุง (24 ตุลาคม 2026)

- หน้าเว็บหลักยังเป็น `deployment/streamlit_app.py` และใช้ `skn_app/ui.py` ร่วมกับหน้าเปิดบนเครื่องเดิม ไม่มีแอปสาธิตแยก
- เมนู: หน้าหลัก / ตรวจจับจากภาพ / ตรวจจับจากวิดีโอ / ผลการทดสอบโมเดล / เกี่ยวกับโครงงาน / คำแนะนำการใช้งาน
- หน้าแรกและหน้าข้อมูลไม่เรียกโมเดล การตรวจจับยังเริ่มเมื่อผู้ใช้กดปุ่มเท่านั้น
- ชื่อประเภทและคอลัมน์แปลเฉพาะหน้าจอ ไม่เปลี่ยนรหัสคลาส เกณฑ์ความเชื่อมั่น หรือรูปแบบ CSV
- กรอบบนภาพและเวลาบนวิดีโอยังคงภาษาอังกฤษจากตัววาดเดิม พร้อมคำอธิบายสีภาษาไทยบนหน้าเว็บ
- ใช้ Noto Sans Thai ผ่าน Google Fonts ในเบราว์เซอร์เท่านั้น หากโหลดไม่ได้จะใช้ Prompt, Tahoma หรือ sans-serif ไม่มีการดาวน์โหลดฟอนต์ในขั้นตอนตรวจจับ
- ปุ่มอัปโหลด เมนูของ Streamlit และคำสั่งจากเบราว์เซอร์บางส่วนยังอาจเป็นภาษาอังกฤษ ไม่แก้ด้วยสคริปต์แทรกหรือซ่อนปุ่มที่กระทบการเข้าถึง
- หน้าผลการทดสอบเป็นค่าคงที่ที่ตรวจสอบจาก `results/skn1_optimization/20261023T101106Z_nms30_c2ce10e9b2/baseline_metrics.json` และ `per_class_baseline.csv` ในโครงงานวิจัยเดิม ไม่ได้คัดลอกชุดข้อมูลหรือผลทดลองทั้งโฟลเดอร์
- ผลทั้งหมดในหน้านี้เป็น Validation: 315 ภาพ / 805 วัตถุ, COCO maxDet 300, NMS 0.30, เก็บความเชื่อมั่นตั้งแต่ 0.001; Precision/Recall/F1 ที่ 0.25 และ IoU 0.50 ไม่ใช่ค่ารับรองทางการแพทย์
- การปรับหน้าจอไม่ได้ยืนยันสิทธิ์เผยแพร่น้ำหนักโมเดล และไม่ได้อนุญาตให้เปิดบริการออนไลน์ใหม่ สถานะสิทธิ์ยัง `LICENSE_UNVERIFIED`
- การตรวจหน้าจอใช้ไฟล์สังเคราะห์และปิดการโหลดโมเดลจริง หลักฐานหน้าจออยู่เฉพาะ `reports/ui_redesign/` ซึ่งไม่เผยแพร่ผ่าน Git
- ยังต้องได้รับอนุญาตก่อน Commit / Push / Deploy UI ฉบับนี้ และตรวจการทำงานบนคลาวด์จริงหลังนำขึ้น
