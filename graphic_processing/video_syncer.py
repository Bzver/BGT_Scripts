import cv2
import numpy as np

def sync_and_trim_videos(video1_path, video2_path, output1_path, output2_path, max_preview_width=1280):
    cap1 = cv2.VideoCapture(video1_path)
    cap2 = cv2.VideoCapture(video2_path)
    
    if not cap1.isOpened() or not cap2.isOpened():
        raise ValueError("Could not open one or both video files. Check paths.")

    fps = cap1.get(cv2.CAP_PROP_FPS)
    len1 = int(cap1.get(cv2.CAP_PROP_FRAME_COUNT))
    len2 = int(cap2.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_w1, orig_h1 = int(cap1.get(3)), int(cap1.get(4))
    orig_w2, orig_h2 = int(cap2.get(3)), int(cap2.get(4))

    max_offset = max(len1, len2)
    win_name = "Sync Preview"
    cv2.namedWindow(win_name)
    cv2.createTrackbar("Offset (frames)", win_name, 0, max_offset, lambda x: None)

    print("🎛️ Controls:")
    print("  • SPACE : Play / Pause")
    print("  • ← / → : Step 1 frame (also works: a / d  or  , / .)")
    print("  • - / + : Adjust offset by ±1 frame")
    print("  • ENTER : Confirm & save")
    print("  • ESC   : Quit")

    playing = False
    last_offset = -1
    pos1 = pos2 = 0
    need_seek = True

    while True:
        offset = cv2.getTrackbarPos("Offset (frames)", win_name)
        start1 = max(0, offset)
        end1 = min(len1, offset + len2)

        # Handle offset changes (trackbar or keyboard)
        if offset != last_offset:
            last_offset = offset
            pos1 = start1
            pos2 = max(0, start1 - offset)
            need_seek = True
            playing = False

        # Block when paused, short timeout when playing
        key = cv2.waitKey(0 if not playing else 30)

        if key == -1:
            pass  # No key pressed
        elif key == 32:  # SPACE
            playing = not playing
        elif key in (81, 2424832, ord('a'), ord(',')):  # LEFT
            playing = False
            pos1 = max(start1, pos1 - 1)
            pos2 = max(0, pos1 - offset)
            need_seek = True
        elif key in (83, 2555904, ord('d'), ord('.')):  # RIGHT
            playing = False
            pos1 += 1
            pos2 += 1
            if pos1 >= end1:  # Loop to start of overlap
                pos1 = start1
                pos2 = max(0, start1 - offset)
            need_seek = True
        elif key == ord('-'):  # Decrease offset
            cv2.setTrackbarPos("Offset (frames)", win_name, max(0, offset - 1))
            need_seek = True
            continue
        elif key in (ord('+'), ord('=')):  # Increase offset
            cv2.setTrackbarPos("Offset (frames)", win_name, min(max_offset, offset + 1))
            need_seek = True
            continue
        elif key in (13, 10):  # ENTER
            confirmed_offset = offset
            break
        elif key == 27:  # ESC
            print("❌ Cancelled.")
            cap1.release(); cap2.release(); cv2.destroyAllWindows()
            return

        # Seek only when position actually changed
        if need_seek:
            cap1.set(cv2.CAP_PROP_POS_FRAMES, pos1)
            cap2.set(cv2.CAP_PROP_POS_FRAMES, pos2)
            need_seek = False

        ret1, f1 = cap1.read()
        ret2, f2 = cap2.read()

        # Fallback if read fails (e.g., end of file)
        if not ret1 or not ret2:
            pos1, pos2 = start1, max(0, start1 - offset)
            cap1.set(cv2.CAP_PROP_POS_FRAMES, pos1)
            cap2.set(cv2.CAP_PROP_POS_FRAMES, pos2)
            ret1, f1 = cap1.read()
            ret2, f2 = cap2.read()

        if playing:
            pos1 += 1
            pos2 += 1
            if pos1 >= end1:
                pos1 = start1
                pos2 = max(0, start1 - offset)
                need_seek = True  # Looping requires a seek

        if f1 is None or f2 is None:
            continue

        # --- PREVIEW SCALING ---
        f1_disp, f2_disp = f1.copy(), f2.copy()
        h1, w1 = f1_disp.shape[:2]
        h2, w2 = f2_disp.shape[:2]
        if h1 != h2:
            target_h = min(h1, h2)
            f1_disp = cv2.resize(f1_disp, (int(w1 * target_h / h1), target_h))
            f2_disp = cv2.resize(f2_disp, (int(w2 * target_h / h2), target_h))

        combined = np.hstack((f1_disp, f2_disp))
        h_c, w_c = combined.shape[:2]
        if w_c > max_preview_width:
            scale = max_preview_width / w_c
            combined = cv2.resize(combined, (int(w_c * scale), int(h_c * scale)))

        # Overlay status
        status = "⏸ PAUSED" if not playing else "▶ PLAYING"
        cv2.putText(combined, f"{status} | Frame: {pos1}/{len1} | Offset: {offset}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow(win_name, combined)

    cv2.destroyAllWindows()
    print(f"✅ Confirmed offset: {confirmed_offset} frames")

    # --- SAVE OVERLAPPING SEGMENTS (Original Resolution) ---
    start1 = max(0, confirmed_offset)
    end1 = min(len1, confirmed_offset + len2)
    duration = end1 - start1

    if duration <= 0:
        print("⚠️  No overlapping frames to save.")
        return

    print(f"💾 Saving {duration} frames ({duration/fps:.2f}s) at original quality...")

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out1 = cv2.VideoWriter(output1_path, fourcc, fps, (orig_w1, orig_h1))
    out2 = cv2.VideoWriter(output2_path, fourcc, fps, (orig_w2, orig_h2))

    cap1.set(cv2.CAP_PROP_POS_FRAMES, start1)
    cap2.set(cv2.CAP_PROP_POS_FRAMES, max(0, start1 - confirmed_offset))

    for i in range(duration):
        ret1, f1 = cap1.read()
        ret2, f2 = cap2.read()
        if ret1 and ret2:
            out1.write(f1)
            out2.write(f2)
            if (i + 1) % 100 == 0 or i == duration - 1:
                print(f"   Progress: {(i+1)/duration*100:.1f}%")
        else:
            break

    out1.release(); out2.release(); cap1.release(); cap2.release()
    print(f"🎉 Done! Saved to:\n  📄 {output1_path}\n  📄 {output2_path}")



if __name__ == "__main__":
    # Replace with your actual file paths
    sync_and_trim_videos(
        video1_path=r"D:\Data\20260513_20260513142219_20260513142329_142739-proc.mp4",
        video2_path=r"D:\Data\20260513_20260513142220_20260513142330_142739-proc.mp4",
        output1_path=r"D:\Data\401T.mp4",
        output2_path=r"D:\Data\401F.mp4",
        max_preview_width=1900
    )