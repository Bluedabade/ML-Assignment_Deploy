// Fixed local assets only. Media is sent solely through Streamlit on explicit confirmation.
export default function ({parentElement, setStateValue, data}) {
  parentElement.innerHTML = `<style>
  .recorder{font-family:inherit;color:var(--st-text-color,inherit);padding:12px;border:1px solid #78909c;border-radius:14px}
  .recorder video{width:100%;max-height:300px;object-fit:contain;background:#142637;border-radius:10px}
  .recorder .actions{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
  .recorder button,.recorder a{padding:10px;border-radius:10px;border:1px solid #0d9488;background:#0f766e;color:white;font:inherit;cursor:pointer;text-decoration:none}
  .recorder button:disabled{opacity:.45;cursor:default}.recorder button:focus-visible,.recorder a:focus-visible{outline:3px solid #fbbf24;outline-offset:2px}
  .recorder p{line-height:1.6;overflow-wrap:anywhere}.recorder a[hidden]{display:none}
  </style><section class="recorder" aria-label="บันทึกวิดีโอด้วยกล้อง">
  <video muted playsinline aria-label="ดูตัวอย่างวิดีโอ"></video>
  <p role="status" aria-live="polite">กดเปิดกล้องเพื่อเริ่มต้น ยังไม่มีการเข้าถึงกล้อง</p>
  <div class="actions"><button data-open>เปิดกล้อง</button><button data-start disabled>เริ่มบันทึก</button><button data-stop disabled>หยุดบันทึก</button></div>
  <div class="actions"><button data-use disabled>ใช้วิดีโอนี้</button><button data-retake>ถ่ายวิดีโอใหม่</button><a hidden download="recording.webm">ดาวน์โหลดวิดีโอต้นฉบับ</a></div>
  <p>ไม่บันทึกเสียง · ไม่เกิน 12 วินาที / 20 MiB<br>กดใช้วิดีโอนี้เพื่อส่งคลิปไปยังเซิร์ฟเวอร์ Streamlit ชั่วคราว จากนั้นกดเริ่มวิเคราะห์วิดีโอ</p></section>`;
  const root=parentElement.querySelector('.recorder'), video=root.querySelector('video'), status=root.querySelector('[role=status]');
  const open=root.querySelector('[data-open]'),start=root.querySelector('[data-start]'),stop=root.querySelector('[data-stop]'),use=root.querySelector('[data-use]'),retake=root.querySelector('[data-retake]'),download=root.querySelector('a');
  let stream=null, recording=null, chunks=[], bytes=0, blob=null, url=null, interval=null, deadline=null, reader=null, disposed=false, invalid=false, opening=false, begun=0, seconds=0, epoch=0;
  const setStatus=s=>{status.textContent=s;};
  const tracks=()=>{if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;};
  const timers=()=>{clearInterval(interval);clearTimeout(deadline);};
  const revoke=()=>{if(url)URL.revokeObjectURL(url);url=null;download.hidden=true;};
  const halt=()=>{timers();if(recording?.state==='recording')recording.stop();tracks();};
  const reset=()=>{epoch++;invalid=true;halt();if(reader)reader.abort();chunks=[];blob=null;revoke();video.removeAttribute('src');video.controls=false;start.disabled=true;stop.disabled=true;use.disabled=true;open.disabled=false;setStatus('กดเปิดกล้องเพื่อถ่ายวิดีโอใหม่');};
  open.onclick=async()=>{
    if(opening)return;
    if(!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder){setStatus('เบราว์เซอร์นี้ไม่รองรับการบันทึก กรุณาอัปโหลด MP4 แทน');return;}
    reset();invalid=false;opening=true;open.disabled=true;
    try{
      const media=await navigator.mediaDevices.getUserMedia({audio:false,video:{width:{ideal:1280,max:1280},height:{ideal:720,max:720},frameRate:{ideal:15,max:15},aspectRatio:{ideal:16/9}}});
      if(disposed||invalid){media.getTracks().forEach(t=>t.stop());return;}
      stream=media;const settings=media.getVideoTracks()[0].getSettings();
      if(!settings.width||!settings.height||settings.width*settings.height>1280*720||Math.max(settings.width,settings.height)>1280)throw new Error();
      video.srcObject=media;video.muted=true;await video.play();start.disabled=false;setStatus('กล้องพร้อมแล้ว กดเริ่มบันทึก');
    }catch(_){tracks();open.disabled=false;setStatus('ไม่สามารถเข้าถึงกล้องได้ กรุณาตรวจสอบสิทธิ์ในเบราว์เซอร์ หรือเลือกอัปโหลดวิดีโอแทน');}
    finally{opening=false;}
  };
  start.onclick=()=>{
    const mime=['video/mp4;codecs=avc1.42E01E','video/mp4','video/webm;codecs=vp8','video/webm;codecs=vp9','video/webm'].find(m=>MediaRecorder.isTypeSupported(m));
    if(!mime||!stream){tracks();open.disabled=false;setStatus('ไม่พบรูปแบบบันทึกที่รองรับ กรุณาอัปโหลด MP4 แทน');return;}
    chunks=[];bytes=0;invalid=false;begun=performance.now();start.disabled=true;stop.disabled=false;use.disabled=true;
    try{recording=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:1500000});}
    catch(_){tracks();open.disabled=false;stop.disabled=true;setStatus('เริ่มบันทึกไม่ได้ กรุณาอัปโหลด MP4 แทน');return;}
    const current=epoch, rec=recording;
    recording.ondataavailable=e=>{if(current===epoch&&!invalid&&e.data.size){bytes+=e.data.size;if(bytes>data.maxBytes){invalid=true;halt();setStatus('วิดีโอเกิน 20 MiB กรุณาถ่ายใหม่หรืออัปโหลด MP4');}else chunks.push(e.data);}};
    recording.onerror=()=>{if(current!==epoch)return;invalid=true;halt();open.disabled=false;stop.disabled=true;setStatus('บันทึกไม่สำเร็จ กรุณาถ่ายใหม่');};
    recording.onstop=()=>{
      if(current!==epoch)return;
      timers();tracks();stop.disabled=true;open.disabled=false;
      if(disposed||invalid){chunks=[];return;}
      blob=new Blob(chunks,{type:rec.mimeType});chunks=[];
      if(!blob.size||blob.size>data.maxBytes){blob=null;setStatus('ขนาดวิดีโอไม่ผ่านข้อจำกัด กรุณาถ่ายใหม่');return;}
      revoke();url=URL.createObjectURL(blob);video.src=url;video.controls=true;video.muted=true;
      download.href=url;download.download=blob.type.startsWith('video/mp4')?'recording.mp4':'recording.webm';download.hidden=false;use.disabled=false;setStatus('บันทึกวิดีโอสำเร็จ ดูตัวอย่างแล้วกดใช้วิดีโอนี้');
    };
    const tick=()=>setStatus(`กำลังบันทึก 00:${String(Math.min(12,Math.floor((performance.now()-begun)/1000))).padStart(2,'0')} / 00:12`);
    recording.start(250);tick();interval=setInterval(tick,200);
    // Small encoding headroom; backend still enforces the unchanged 12-second limit.
    deadline=setTimeout(()=>stop.click(),Math.min(data.maxSeconds*1000,11800));
  };
  stop.onclick=()=>{seconds=Math.min(data.maxSeconds,(performance.now()-begun)/1000);halt();};
  use.onclick=()=>{
    if(!blob||use.disabled)return;use.disabled=true;reader=new FileReader();const current=epoch;
    reader.onload=()=>{if(current===epoch&&!disposed&&blob){setStateValue('clip',{b64:String(reader.result).split(',')[1],mime:blob.type.split(';')[0],seconds});setStatus('ส่งวิดีโอแล้ว กดเริ่มวิเคราะห์วิดีโอด้านข้าง');}};
    reader.onerror=()=>{use.disabled=false;setStatus('ส่งวิดีโอไม่สำเร็จ กรุณาถ่ายใหม่');};reader.readAsDataURL(blob);
  };
  retake.onclick=()=>{reset();setStateValue('clip',null);};
  const hidden=()=>{if(document.hidden){reset();setStatus('หยุดกล้องแล้วเมื่อออกจากหน้าจอ กรุณาเปิดใหม่');}};
  document.addEventListener('visibilitychange',hidden);window.addEventListener('pagehide',reset);
  return ()=>{disposed=true;reset();document.removeEventListener('visibilitychange',hidden);window.removeEventListener('pagehide',reset);open.onclick=start.onclick=stop.onclick=use.onclick=retake.onclick=null;};
}
