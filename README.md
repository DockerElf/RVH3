# RVH3
Viggle H3 UI Helper

# PREREQUISITES:
1. Comfy Desktop, open Roggle_UI/viggle_auto/step3.1_api.json and step4_api.json in Comfy Desktop and resolve all node/model errors to make sure you have all the extension and models installed.
2. Qwen 2.1 and loras as per BFS Best Face Swap https://huggingface.co/Alissonerdx/BFS-Best-Face-Swap/blob/main/docs/qwen-image-2.1-body.md
3. nodes and loras as per Viggle long workflow (advanced)
https://huggingface.co/drbaph/Viggle-Animate-ComfyUI

 
# INSTALL STEPS
1. navigate to Roggle_UI/viggle_auto
2. clone config.json.template to config.json
3. set the paths correctly, these are optional
    "comfy_input_directory"
    "comfy_output_directory"
    "comfy_staging_subdir"
    "step3_output_subdir"
    "step4_output_subdir"
4. Roggle_UI/run.bat

# USAGE
Step 1.
- Browse and pick target references on the left panel, hit SAVE
- Browse Videos and hit ＋ Add Shot to build shot list
- you can edit the shot list on the right panel

Step 2.
- Press Step 2 button on the right panel
- it will extract screenshot .PNG and small duration .MP4 clip in Roggle_UI/viggle_auto/step34input

Step 3. 
- Prompt Qwen2.1 properly in the right panel, hit SAVE
- Press Step 3 button on the right panel
- it will start Comfy Desktop backend without the GUI
- Qwen 2.1 will use each .PNG screenshot and inpaint the target references to the screenshot to create an inpainted .PNG

Step 4.
- Press Step 4 button on the right panel
- Viggle will animate the inpainted .PNG from Step 3 with the small duration MP4 clip from Step 2

MISC.
- to re-run exact job, remove it from the job list and hit save. job list are in Roggle_UI/viggle_auto/run_state.json
- both Qwen2.1 prompt and static target references are in viggle_auto/config.json
- manual cleanup needed for Comfy/input/viggle_auto and Comfy/output/viggle_auto when it builds up
