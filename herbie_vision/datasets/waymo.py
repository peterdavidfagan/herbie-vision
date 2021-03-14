import os
import sys
import json

import numpy as np
import pandas as pd
from PIL import Image
import cv2
import argparse

import torch
import torch.utils.data as data

from herbie_vision.utils.image import annotations_to_df, process_resizing
from herbie_vision.utils.gcp_utils import download_blob, upload_blob

from google.cloud import storage


def collate_fn(batch):
    return tuple(zip(*batch))

class WaymoDataset(data.Dataset):
    def __init__(self, mount_dir, gcp_annotations_path, cat_names, cat_ids, resize, area_limit):
        super(WaymoDataset, self).__init__()
        
        # filepaths
        self.gcp_annotations_path = gcp_annotations_path
        self.mount_dir = mount_dir

        self.dataset_name =  self.gcp_annotations_path.split('/')[-1].replace('.json','')
        self.dataset_path =  self.mount_dir +'/'.join(self.gcp_annotations_path.split('/')[:-2]) 
        self.path_to_annotations = self.mount_dir + self.gcp_annotations_path
        self.path_to_processed_images = self.dataset_path+'/processed_images/'
        self.path_to_metadata = self.dataset_path + '/metadata/'
        
        # high level summary values
        self.num_classes = len(cat_names)
        self.category_names = cat_names
        self.category_ids = cat_ids
        self.resize = resize
        self.area_limit = area_limit
        
        # setup data directory
        print('Setting up data directories...')
        if os.path.exists(self.path_to_processed_images)==False:
            os.mkdir(self.path_to_processed_images)

            # read annotations file
            f = open(self.path_to_annotations,'r')
            self.annotations = json.load(f)
            f.close()
            
            # convert annotations to dataframe
            print('Processing images...')
            image_map = {entry['id']:'/'+'/'.join(entry['gcp_url'].split('/')[3::]) for entry in annotations['images']}
            self.annotations_df = annotations_to_df(self.annotations, self.mount_dir, image_map)
            self.annotations_df['category_id'] = self.annotations_df['category_id'].apply(lambda x: 3 if x==4 else x) # map so categories are contiguous
            
            # Preprocess images to be the same size
            print('Processing images...')
            self.annotations_df = process_resizing(self.path_to_processed_images, self.annotations_df, resize)
            self.annotations_df.to_csv(self.path_to_annotations + '/processed_annotations.csv')
        else:
            # read in annotations
            self.annotations_df = pd.read_csv('/'.join(self.path_to_annotations.split('/')[:-1]) + '/processed_annotations.csv')

        # Drop bounding boxes which are too small
        self.annotations_df['r_area'] = (self.annotations_df['xr_max'] - self.annotations_df['xr_min'])*(self.annotations_df['yr_max'] - self.annotations_df['yr_min'])
        self.annotations_df = self.annotations_df[self.annotations_df['r_area']>self.area_limit]
        

        # Drop images without annotations
        self.annotations['images'] = [x for x in self.annotations['images'] if x['id'] in self.annotations_df['image_id'].unique()]
        self.annotations['images'] = [x for x in self.annotations['images'] if x['id'] in self.annotations_df['image_id'].unique()]
        
        
        
            
            
    def __getitem__(self, idx):
        image_id = self.annotations['images'][idx]['id']
        image_url = self.annotations['images'][idx]['gcp_url']
        filename = image_url.split('/')[-1]
        image = cv2.imread(self.local_path_to_processed_images+'{}'.format(filename))
        image = torch.tensor(image).permute(2,0,1).float()        
        
        # define target data for fast rcnn
        temp_df = self.annotations_df[self.annotations_df['image_id']==image_id]

        boxes = []
        labels = []
        areas = []
        for _,item in temp_df.iterrows():
            boxes.append([item['xr_min'],item['yr_min'],item['xr_max'],item['yr_max']])
            labels.append(item['category_id'])
            areas.append(item['area'])
        
        boxes = torch.tensor(boxes, dtype=torch.int64)
        areas = torch.tensor(areas, dtype=torch.int64)
        labels = torch.tensor(labels, dtype=torch.int64)
        
        target = {}
        target["boxes"] = boxes
        target["labels"] = labels
        target["image_id"] = torch.tensor(idx)
        target["area"] = areas
        
        return image, target
    
    def __len__(self):
        return len(self.annotations['images'])