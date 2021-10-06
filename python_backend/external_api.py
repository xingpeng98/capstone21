from app import app
from flask import request, send_file
from flask_cors import CORS, cross_origin
from utils import crop_image, render_image, create_directories, plot_keypoints, save_image

import json
import os
from datetime import datetime
CORS(app)

import sys
sys.path.insert(1, 'triton_client/model_client')
from triton_client.model_client.lpd_model_class import LpdModelClass
from triton_client.model_client.lpr_model_class import LprModelClass
from triton_client.model_client.bodyposenet_model_class import BodyPoseNetClass


BASE_URL = 'http://localhost:5000/'
@app.route('/api/lpdnet/<id>',methods= ['POST', 'GET'])
def call_lpdnet(id):

    """
    This function responds to the external API call of obtaining
    lpdnet

    :return: JSON object 
    """
    
    lpd = LpdModelClass(id)

    if request.method=='GET':
        return lpd.status()
    
    elif request.method=='POST':

        # Create directories for input and output images
        now = datetime.now()
        curr_time = now.strftime("%d%m%y_%H%M%S")
        create_directories('lpdnet',id, curr_time)

        # Load input images
        # input_stream = request.files['image']
        files = request.files.to_dict(flat=False)['image']

        # Load filenames
        filenames = request.form.getlist('filename')
        
        images = {}
        # Save input images
        for i, f in enumerate(files):
            images[filenames[i]] = f
            f.save(f"triton_client/lpdnet/input/{id}/{curr_time}/{filenames[i]}")
        
        # Call triton inference server
        response = lpd.predict(f"triton_client/lpdnet/input/{id}/{curr_time}")
        
        # Process response to return
        processed = {}
        for i, info in enumerate(response):
            if info['HTTPStatus']==204:
                # No inference bounding box was found
                processed[i] = info
            else:
                # info is a list of bbox, bbox is a dict containing a list (bbox)
                # and a single number, confidence score
                for j, bbox_info in enumerate(info["all_bboxes"]):
                    crop_image(images[info['file_name']],bbox_info['bbox'],f"triton_client/lpdnet/output/{id}/{curr_time}/{j}_{info['file_name']}")
                if id=='internal':
                    render_image(images[info['file_name']],info["all_bboxes"],f"triton_client/lpdnet/output/overlay_lpdnet_{info['file_name']}")
                    info['overlay_image'] = f"triton_client/lpdnet/output/overlay_lpdnet_{info['file_name']}"
                processed[i] = info
        return processed        
    
    else:
        return {'code':404,'error':'Request not found'}
    

@app.route('/api/lprnet/<id>',methods= ['POST', 'GET'])
def call_lprnet(id):

    """
    This function responds to the external API call of obtaining
    lprnet

    :return: JSON object 
    """
    
    lpr = LprModelClass(id)

    if request.method=='GET':

        return lpr.status()
    
    elif request.method=='POST':

        # Create directories for input and output images
        now = datetime.now()
        curr_time = now.strftime("%H%M%S")
        create_directories('lprnet',id, curr_time)

        # Load input images
        # input_stream = request.files['image']
        files = request.files.to_dict(flat=False)['image']

        # Load filenames
        filenames = request.form.getlist('filename')
        
        images = {}
        # Save input images
        for i, f in enumerate(files):
            images[filenames[i]] = f
            f.save(f"triton_client/lprnet/input/{id}/{curr_time}/{filenames[i]}")
        
        # Call triton inference server
        response = lpr.predict(f"triton_client/lprnet/input/{id}/{curr_time}")
        
        # Process response to return
        processed = {}
        for i, info in enumerate(response):
            processed[i] = info
        return processed        
    
    else:
        return {'code':404,'error':'Request not found'}


@app.route('/api/lpdlprnet/<id>',methods= ['POST', 'GET'])
def call_combined(id):

    """
    This function responds to the external API call of obtaining
    lpd and then lpr.

    :return: JSON object 
    """
    
    lpr = LprModelClass(id)
    lpd = LpdModelClass(id)

    if request.method=='GET':

        return lpr.status()
    
    elif request.method=='POST':

        # Create directories for input and output images
        now = datetime.now()
        curr_time = now.strftime("%H%M%S")
        create_directories('lpdnet',id, curr_time)
        create_directories('lprnet',id, curr_time)

        # Load input images
        files = request.files.to_dict(flat=False)['image']

        # Load filenames
        filenames = request.form.getlist('filename')
        
        images = {}
        # Save input images
        for i, f in enumerate(files):
            images[filenames[i]] = f
            f.save(f"triton_client/lpdnet/input/{id}/{curr_time}/{filenames[i]}")
        
        # Call triton inference server
        lpd_response = lpd.predict(f"triton_client/lpdnet/input/{id}/{curr_time}")

        # Save the lpd output images into a new folder
        processed = {}
        reverse_mapping = {}
        for i, info in enumerate(lpd_response):
            if info['HTTPStatus']==204:
                # No inference bounding box was found
                processed[i] = info
            else:
                # info is a list of bbox, bbox is a dict containing a list (bbox)
                # and a single number, confidence score
                for j, bbox_info in enumerate(info["all_bboxes"]):
                    crop_image(images[info['file_name']],bbox_info['bbox'],f"triton_client/lpdnet/output/{id}/{curr_time}/{j}_{info['file_name']}")
                    crop_image(images[info['file_name']],bbox_info['bbox'],f"triton_client/lprnet/input/{id}/{curr_time}/{j}_{info['file_name']}")
                    
                    reverse_mapping[f"{j}_{info['file_name']}"] = i
                    
                    bbox_info[f"{j}_bbox"] = bbox_info.pop('bbox')
                
                if id=='internal':
                    render_image(images[info['file_name']],info['all_bboxes'],f"triton_client/lpdnet/output/overlay_lpdnet_{info['file_name']}")
                    info['overlay_image'] = f"triton_client/lpdnet/output/overlay_lpdnet_{info['file_name']}"

                processed[i] = info

        # Call LPR on output of LPD
        lpr_response = lpr.predict(f"triton_client/lprnet/input/{id}/{curr_time}")

        # Process response to return
        for lpr_info in lpr_response:
            file_name = lpr_info['file_name']
            index = file_name.split("_")[0]
            temp = {}
            temp['license_plate'] = lpr_info['license_plate']
            temp['confidence_scores'] = lpr_info['confidence_scores']
            processed[reverse_mapping[file_name]][f"{index}_lpr"] = temp

        return processed        
    
    else:
        return {'code':404,'error':'Request not found'}


@app.route('/api/lpdlprnet/explain/<id>',methods= ['POST', 'GET'])
def call_explain_combined(id):
    import pandas as pd

    lpr = LprModelClass(id)
    lpd = LpdModelClass(id)

    # Create directories for input and output images
    now = datetime.now()
    curr_time = now.strftime("%H%M%S")
    create_directories('lpdnet',id, curr_time)
    create_directories('lprnet',id, curr_time)

    # Load input images
    files = request.files.to_dict(flat=False)['image']

    # Load filenames
    filenames = request.form.getlist('filename')
    
    images = {}

    # Save input images --> for explain, only use 1st file
    images[filenames[0]] = files[0]
    files[0].save(f"triton_client/lpdnet/input/{id}/{curr_time}/{filenames[0]}")
    
    lpd_response = lpd.predict(f"triton_client/lpdnet/input/{id}/{curr_time}")

    processed = {}
    reverse_mapping = {}
    i, info = 0, lpd_response[0]
    if info['HTTPStatus']==204:
        # No inference bounding box was found
        processed[i] = info
        save_image(images[info['file_name']], f"triton_client/lprnet/input/{id}/{curr_time}/exp_{info['file_name']}")
        reverse_mapping[f"exp_{info['file_name']}"] = i

    else:
        # info is a list of bbox, bbox is a dict containing a list (bbox)
        # and a single number, confidence score
        for j, bbox_info in enumerate(info["all_bboxes"]):
            crop_image(images[info['file_name']],bbox_info['bbox'],f"triton_client/lpdnet/output/{id}/{curr_time}/exp_{info['file_name']}")
            crop_image(images[info['file_name']],bbox_info['bbox'],f"triton_client/lprnet/input/{id}/{curr_time}/exp_{info['file_name']}")
            reverse_mapping[f"exp_{info['file_name']}"] = i
            
            if id=='internal':
                demopic_name=f"triton_client/lpdnet/output/{id}/{curr_time}/overlay_lpdnet_{info['file_name']}"
                render_image(images[info['file_name']],bbox_info['bbox'], demopic_name)
                info['overlay_image'] = demopic_name
            
            bbox_info[f"exp_bbox"] = bbox_info.pop('bbox')

    processed[i] = info


     # Call LPR on output of LPD
    lpr_response = lpr.predict(f"triton_client/lprnet/input/{id}/{curr_time}")

    # Process response to return
    for lpr_info in lpr_response:
        file_name = lpr_info['file_name']
        index = file_name.split("_")[0]
        temp = {}
        temp['license_plate'] = list(lpr_info['license_plate'])
        temp['confidence_scores'] = lpr_info['confidence_scores']
        processed[reverse_mapping[file_name]][f"exp_lpr"] = temp
     
        
    # replace markdown placeholders with custom images
    image_replace = {
        '%placeholder1%' : f"{BASE_URL}/api/get_image?path=triton_client/lpdnet/input/{id}/{curr_time}/{filenames[i]}", 
        '%placeholder2%' : f"{BASE_URL}/api/get_image?path=triton_client/lpdnet/output/{id}/{curr_time}/overlay_lpdnet_{info['file_name']}",
        '%placeholder3%' : f"{BASE_URL}/api/get_image?path=triton_client/lpdnet/output/{id}/{curr_time}/exp_{info['file_name']}",
        '%placeholder5%' : pd.DataFrame(info['all_bboxes']).to_html(),
        '%placeholder6%' : pd.DataFrame(temp).assign(lp = '')[['lp', 'license_plate', 'confidence_scores']].rename(columns={'lp':lpr_info['license_plate']}).to_html(index=False, ),
    }
    with open("database/lpdlprnet/lpdlprnet_explainability.md", 'r') as md:
        text = md.readlines()
        lines = []
        for line in text: 
            lines.append(line)
            for key in image_replace.keys(): 
                if key in line: 
                    lines[-1] = line.replace(key, image_replace[key])
                
          
        new_text = "\n".join(lines)
    
    return {'explain_markdown': new_text}


@app.route('/api/bpnet/<id>',methods= ['POST', 'GET'])
def call_bpnet(id):

    """
    This function responds to the external API call of obtaining
    lpdnet

    :return: JSON object 
    """
    
    bpn = BodyPoseNetClass(id)

    if request.method=='GET':
        return bpn.status()
    
    elif request.method=='POST':

        # Create directories for input and output images
        now = datetime.now()
        curr_time = now.strftime("%d%m%y_%H%M%S")
        create_directories('bpnet',id, curr_time)

        # Load input images
        # input_stream = request.files['image']
        files = request.files.to_dict(flat=False)['image']

        # Load filenames
        filenames = request.form.getlist('filename')
        
        images = {}
        # Save input images
        for i, f in enumerate(files):
            images[filenames[i]] = f
            f.save(f"triton_client/bpnet/input/{id}/{curr_time}/{filenames[i]}")
        
        # Call triton inference server
        response = bpn.predict(f"triton_client/bpnet/input/{id}/{curr_time}")
        #return str(response['results'])
        # Process response to return
        processed = {}
        for file_name, info in response['results'].items():
            # info is a list of keypoints corresponding to number of people identified
            # keypoints is a dict containing a numpy array (coordinates)
            # and confidence score and a number "total" 
            # corresponding to the number of key points identified
            user_list = {}
            for i, keypoints in enumerate(info):
                temp = {}
                for k, v in keypoints.items():
                    if k in ['total','score']:
                        temp[k] = v
                    else:
                        temp[k] = v.tolist()
                user_list[str(i)] = temp
            processed[file_name] = user_list
            
            if id=='internal':
                output_path = f"triton_client/bpnet/output/{id}/{curr_time}/{file_name}"
                plot_keypoints(response,file_name,f"triton_client/bpnet/input/{id}/{curr_time}/{file_name}",output_path)
                processed[file_name]['overlay_image'] = output_path
        
        return processed        
    
    else:
        return {'code':404,'error':'Request not found'}

