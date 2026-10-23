# ร่างข้อความขอยืนยันสิทธิ์ — ยังไม่ได้ส่ง

ผู้ใช้ควรตรวจแก้แล้วติดต่อ Roboflow support/เจ้าของ SKN และผู้ถือสิทธิ์ที่เกี่ยวข้องด้วยตนเอง ไม่ใส่ API key, Request URLs, Cached weights, ภาพใบหน้าหรือ Credentials ในข้อความ

Subject: Clarification of skn-1/2 YOLO-NAS weights licensing for an educational Streamlit demo

Hello,

I am preparing a non-commercial university project using the SKN-1 model at https://universe.roboflow.com/skn-f1vaw/skn-1, model ID skn-1/2. The project page identifies YOLO-NAS and checkpoint coco/14. The page lists a CC BY4.0 license, while the YOLO-NAS documentation distinguishes the source-code license from the pretrained weights license.

Could you please confirm:

1. Who owns and licenses the exact model weights supplied by the official inference-models SDK for skn-1/2?
2. What base weights/checkpoint were used, and what inherited license terms apply?
3. Is self-hosted ONNX CPU inference on Streamlit Community Cloud permitted for an educational demo accessed by a professor through a URL? Please distinguish private access from public access.
4. Does this use require written consent under the YOLO-NAS remote-access/managed-service restrictions? If so, who can grant it?
5. What attribution, notices, access controls, retention limits, and other conditions are required?
6. May the official SDK provision the package into ephemeral private server storage, without redistributing weights in GitHub or another public storage service?

Uploaded user media would be processed only in the application runtime and not sent to a third-party inference API. The source-only GitHub repository and CI do not contain, download, or execute model weights. No inference service will be published until these permissions are clear.

Please provide the applicable license text or written authorization, including any conditions. Thank you.
