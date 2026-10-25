# SceneForge AI — Video Pack

This folder contains verified, rendered video outputs across all supported aspect ratios (16:9, 9:16, 1:1) and input modes (Text-to-Video with gTTS speech synthesis and Audio-to-Video with SpeechRecognition STT transcription).

## Video Pack Contents

1. `job_16x9_script_pixabay/`:
   - Job ID: `a89874ff-b596-43d5-b95e-6cec68a7d441`
   - Aspect ratio: `16:9 (1920x1080 @ 30 FPS)`
   - Input: Script prompt with gTTS voiceover synthesis
   - Footage: Genuine Pixabay B-roll (`pixabay-309208` ocean waves, `pixabay-116732` city night lights)
   - Codec: H.264 video, AAC audio, duration 8.76s, size 9.3 MB
   - QA: PASS (16/16 checks)

2. `job_16x9_audio_only_stt/`:
   - Job ID: `c6e7e5b1-42ac-4f55-bb1a-98f43fc5f301`
   - Aspect ratio: `16:9 (1920x1080 @ 30 FPS)`
   - Input: Uploaded audio voiceover recording (`voiceover_lake.mp3`) with SpeechRecognition STT transcription
   - Footage: Genuine Pixabay B-roll (`pixabay-199554` mountain lake & evergreen trees)
   - Codec: H.264 video, AAC audio, duration 6.93s, size 5.47 MB
   - QA: PASS (16/16 checks)

3. `job_9x16_portrait/`:
   - Job ID: `ca9aa9d4-9769-4fda-963e-a77e8ac984e3`
   - Aspect ratio: `9:16 Portrait (1080x1920 @ 30 FPS)`
   - Framing: Geometric reframing with blurred-padding / center-crop
   - Codec: H.264 video, AAC audio

4. `job_1x1_square/`:
   - Job ID: `1d7b1d2d-9932-408e-b75f-ffaa5199572d`
   - Aspect ratio: `1:1 Square (1080x1080 @ 30 FPS)`
   - Framing: Square center-crop / pad
   - Codec: H.264 video, AAC audio

5. `job_16x9_alpine_lake/`:
   - Job ID: `8ce5ae31-f3e4-4856-b951-201baabcffd9`
   - Aspect ratio: `16:9 (1920x1080 @ 30 FPS)`
   - Footage: Pixabay alpine lake (`pixabay-380291` & `pixabay-311442`)
   - Codec: H.264 video, AAC audio, duration 8.0s, size 5.65 MB
