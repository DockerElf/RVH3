# RVH3
Viggle H3 UI Helper
<img width="2692" height="1885" alt="image" src="https://github.com/user-attachments/assets/36b32ba0-0e6f-4c55-9237-a67c80788bc3" />


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
Step 1. Shot list
- Browse and pick target references on the left panel, hit SAVE
  <img width="150" alt="image" src="https://github.com/user-attachments/assets/e1e3c627-f215-428c-86ed-fec2b7403d3d" />

- Browse Videos and hit ＋ Add Shot to build shot list
<img width="800" alt="image" src="https://github.com/user-attachments/assets/29e4c1bf-25ea-4a7f-9354-cb9a1cf19b8b" />

- you can edit the shot list on the right panel
<img width="1082" height="422" alt="image" src="https://github.com/user-attachments/assets/78d705c1-f951-429e-aed0-de01a1d4ddd5" />



Step 2. Prepare Clips and Inpaint Frames
- Press Step 2 button on the right panel
- <img width="150" alt="image" src="https://github.com/user-attachments/assets/ed9d9e06-2d2a-4d81-8d38-020a739c28aa" />

- it will extract screenshot .PNG and small duration .MP4 clip in Roggle_UI/viggle_auto/step34input
<img width="800"  alt="image" src="https://github.com/user-attachments/assets/70b568af-9049-4838-a565-cc5207199751" />


Step 3. Inpaint Frames with Target Faces/Body
- Prompt Qwen2.1 properly in the right panel, hit SAVE
 <img width="800" alt="image" src="https://github.com/user-attachments/assets/8c64cde1-cd21-4a20-bcbf-7a68c37fd190" />

- Press Step 3 button on the right panel, it starts Comfy Desktop backend without the GUI
<img width="150"  alt="image" src="https://github.com/user-attachments/assets/d7ca2b42-c184-40f8-96a8-620c66f19f0f" />

- Qwen 2.1 will use each .PNG screenshot and inpaint the target references to the screenshot to create source-target permutation of inpainted .PNG

<img width="800" alt="image" src="https://github.com/user-attachments/assets/fe982eef-8a66-4db2-8fe4-131c06475ef8" />


Step 4.
- Press Step 4 button on the right panel
<img width="150" alt="image" src="https://github.com/user-attachments/assets/916fcb39-fd21-4caa-a7d4-d6a2077b8e7f" />

- Viggle will animate the inpainted .PNG from Step 3 with the small duration MP4 clip from Step 2

MISC.
- to re-run exact job, remove it from the job list and hit save. job list are in Roggle_UI/viggle_auto/run_state.json
- both Qwen2.1 prompt and static target references are in viggle_auto/config.json
- manual cleanup needed for Comfy/input/viggle_auto and Comfy/output/viggle_auto when it builds up
