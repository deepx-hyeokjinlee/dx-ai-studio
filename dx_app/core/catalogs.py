"""DX-APP Processor & Visualizer catalogs for the Compiler Test Wizard."""

_PREPROC_CAT = [
    {"name": "SimpleResizePreprocessor", "label": "Simple Resize (stretch)"},
    {"name": "LetterboxPreprocessor", "label": "Letterbox (keep aspect ratio, padding)"},
    {"name": "GrayscaleResizePreprocessor", "label": "Grayscale Resize"},
]

_POSTPROC_CAT = [
    # ── Classification ──
    {"name": "ClassificationPostprocessor", "label": "Classification (Softmax/Top-K)", "cats": ["classification"]},
    # ── Object Detection ──
    {"name": "YOLOv5Postprocessor", "label": "YOLOv5 Detection", "cats": ["object_detection"]},
    {"name": "YOLOv8Postprocessor", "label": "YOLOv8 Detection", "cats": ["object_detection"]},
    {"name": "YOLOXPostprocessor", "label": "YOLOX Detection", "cats": ["object_detection"]},
    {"name": "DamoYoloPostprocessor", "label": "DamoYOLO Detection", "cats": ["object_detection"]},
    {"name": "SSDPostprocessor", "label": "SSD Detection", "cats": ["object_detection"]},
    {"name": "NanoDetPostprocessor", "label": "NanoDet Detection", "cats": ["object_detection"]},
    {"name": "EfficientDetPostprocessor", "label": "EfficientDet Detection", "cats": ["object_detection"]},
    {"name": "TFLiteDetectionPostprocessor", "label": "TFLite Detection", "cats": ["object_detection"]},
    {"name": "YOLOv5PPUPostprocessor", "label": "YOLOv5 PPU Detection", "cats": ["object_detection"]},
    {"name": "YOLOv7PPUPostprocessor", "label": "YOLOv7 PPU Detection", "cats": ["object_detection"]},
    # ── Face Detection ──
    {"name": "SCRFDPostprocessor", "label": "SCRFD Face Detection", "cats": ["face_detection"]},
    {"name": "ULFGPostprocessor", "label": "ULFG Face Detection", "cats": ["face_detection"]},
    {"name": "SCRFDPPUPostprocessor", "label": "SCRFD PPU Face Detection", "cats": ["face_detection"]},
    {"name": "PalmDetectionPostprocessor", "label": "Palm Detection", "cats": ["face_detection", "hand_landmark"]},
    # ── Segmentation ──
    {"name": "SemanticSegmentationPostprocessor", "label": "Semantic Segmentation", "cats": ["semantic_segmentation"]},
    {"name": "SegFormerPostprocessor", "label": "SegFormer Segmentation", "cats": ["semantic_segmentation"]},
    {"name": "InstanceSegPostprocessor", "label": "Instance Segmentation", "cats": ["instance_segmentation"]},
    {"name": "YOLOv8InstanceSegPostprocessor", "label": "YOLOv8 Instance Seg", "cats": ["instance_segmentation"]},
    {"name": "YOLOv5InstanceSegPostprocessor", "label": "YOLOv5 Instance Seg", "cats": ["instance_segmentation"]},
    # ── Pose Estimation ──
    {"name": "YOLOv5PosePostprocessor", "label": "YOLOv5 Pose", "cats": ["pose_estimation"]},
    {"name": "YOLOv8PosePostprocessor", "label": "YOLOv8 Pose", "cats": ["pose_estimation"]},
    {"name": "YOLOv5PosePPUPostprocessor", "label": "YOLOv5 Pose PPU", "cats": ["pose_estimation"]},
    # ── Hand Landmark ──
    {"name": "HandLandmarkPostprocessor", "label": "Hand Landmark", "cats": ["hand_landmark"]},
    # ── OBB / Depth ──
    {"name": "OBBPostprocessor", "label": "OBB Detection", "cats": ["obb_detection"]},
    {"name": "DepthEstimationPostprocessor", "label": "Depth Estimation", "cats": ["depth_estimation"]},
    # ── Restoration / Enhancement ──
    {"name": "ESPCNPostprocessor", "label": "ESPCN Super Resolution", "cats": ["super_resolution"]},
    {"name": "DnCNNPostprocessor", "label": "DnCNN Denoising", "cats": ["image_denoising"]},
    {"name": "ZeroDCEPostprocessor", "label": "Zero-DCE Enhancement", "cats": ["image_enhancement"]},
    # ── Embedding ──
    {"name": "GenericEmbeddingPostprocessor", "label": "Generic Embedding", "cats": ["embedding"]},
]

_VIS_CAT = [
    {"name": "ClassificationVisualizer", "label": "Classification", "cats": ["classification"]},
    {"name": "DetectionVisualizer", "label": "Detection (BBox)", "cats": ["object_detection", "face_detection", "obb_detection"]},
    {"name": "OBBVisualizer", "label": "OBB Detection", "cats": ["obb_detection"]},
    {"name": "FaceVisualizer", "label": "Face Detection", "cats": ["face_detection"]},
    {"name": "SemanticSegmentationVisualizer", "label": "Semantic Segmentation", "cats": ["semantic_segmentation"]},
    {"name": "InstanceSegVisualizer", "label": "Instance Segmentation", "cats": ["instance_segmentation"]},
    {"name": "PoseVisualizer", "label": "Pose Estimation", "cats": ["pose_estimation"]},
    {"name": "DepthVisualizer", "label": "Depth Estimation", "cats": ["depth_estimation"]},
    {"name": "RestorationVisualizer", "label": "Denoising/Restoration", "cats": ["image_denoising"]},
    {"name": "SuperResolutionVisualizer", "label": "Super Resolution", "cats": ["super_resolution"]},
    {"name": "EnhancementVisualizer", "label": "Image Enhancement", "cats": ["image_enhancement"]},
    {"name": "EmbeddingVisualizer", "label": "Embedding", "cats": ["embedding"]},
    {"name": "HandLandmarkVisualizer", "label": "Hand Landmark", "cats": ["hand_landmark"]},
    {"name": "FaceAlignmentVisualizer", "label": "Face Alignment", "cats": ["face_alignment"]},
]

# postprocessor → recommended visualizer mapping
_POST_TO_VIS = {
    "ClassificationPostprocessor": "ClassificationVisualizer",
    "YOLOv5Postprocessor": "DetectionVisualizer",
    "YOLOv8Postprocessor": "DetectionVisualizer",
    "YOLOXPostprocessor": "DetectionVisualizer",
    "DamoYoloPostprocessor": "DetectionVisualizer",
    "SSDPostprocessor": "DetectionVisualizer",
    "NanoDetPostprocessor": "DetectionVisualizer",
    "EfficientDetPostprocessor": "DetectionVisualizer",
    "TFLiteDetectionPostprocessor": "DetectionVisualizer",
    "YOLOv5PPUPostprocessor": "DetectionVisualizer",
    "YOLOv7PPUPostprocessor": "DetectionVisualizer",
    "SCRFDPostprocessor": "FaceVisualizer",
    "ULFGPostprocessor": "FaceVisualizer",
    "SCRFDPPUPostprocessor": "FaceVisualizer",
    "PalmDetectionPostprocessor": "FaceVisualizer",
    "SemanticSegmentationPostprocessor": "SemanticSegmentationVisualizer",
    "SegFormerPostprocessor": "SemanticSegmentationVisualizer",
    "InstanceSegPostprocessor": "InstanceSegVisualizer",
    "YOLOv8InstanceSegPostprocessor": "InstanceSegVisualizer",
    "YOLOv5InstanceSegPostprocessor": "InstanceSegVisualizer",
    "YOLOv5PosePostprocessor": "PoseVisualizer",
    "YOLOv8PosePostprocessor": "PoseVisualizer",
    "YOLOv5PosePPUPostprocessor": "PoseVisualizer",
    "HandLandmarkPostprocessor": "HandLandmarkVisualizer",
    "OBBPostprocessor": "OBBVisualizer",
    "DepthEstimationPostprocessor": "DepthVisualizer",
    "ESPCNPostprocessor": "SuperResolutionVisualizer",
    "DnCNNPostprocessor": "RestorationVisualizer",
    "ZeroDCEPostprocessor": "EnhancementVisualizer",
    "GenericEmbeddingPostprocessor": "EmbeddingVisualizer",
}

# For factory code generation: postprocessors whose constructor needs only (config)
_POST_CTOR = {}  # default: (w, h, config)

# For factory code generation: visualizers that don't need ()
_VIS_CTOR = {}  # default: ()

# Recommended pipeline combos by category (pre, post, vis)
_CAT_RECOMMEND = {
    "classification":         {"pre": "SimpleResizePreprocessor",      "post": "ClassificationPostprocessor",        "vis": "ClassificationVisualizer"},
    "object_detection":       {"pre": "LetterboxPreprocessor",         "post": "YOLOv8Postprocessor",                "vis": "DetectionVisualizer"},
    "face_detection":         {"pre": "LetterboxPreprocessor",         "post": "SCRFDPostprocessor",                 "vis": "FaceVisualizer"},
    "pose_estimation":        {"pre": "LetterboxPreprocessor",         "post": "YOLOv8PosePostprocessor",            "vis": "PoseVisualizer"},
    "semantic_segmentation":  {"pre": "SimpleResizePreprocessor",      "post": "SemanticSegmentationPostprocessor",  "vis": "SemanticSegmentationVisualizer"},
    "instance_segmentation":  {"pre": "LetterboxPreprocessor",         "post": "YOLOv8InstanceSegPostprocessor",     "vis": "InstanceSegVisualizer"},
    "obb_detection":          {"pre": "LetterboxPreprocessor",         "post": "OBBPostprocessor",                   "vis": "OBBVisualizer"},
    "depth_estimation":       {"pre": "SimpleResizePreprocessor",      "post": "DepthEstimationPostprocessor",       "vis": "DepthVisualizer"},
    "super_resolution":       {"pre": "GrayscaleResizePreprocessor",   "post": "ESPCNPostprocessor",                 "vis": "SuperResolutionVisualizer"},
    "image_denoising":        {"pre": "GrayscaleResizePreprocessor",   "post": "DnCNNPostprocessor",                 "vis": "RestorationVisualizer"},
    "image_enhancement":      {"pre": "SimpleResizePreprocessor",      "post": "ZeroDCEPostprocessor",               "vis": "EnhancementVisualizer"},
    "embedding":              {"pre": "SimpleResizePreprocessor",      "post": "GenericEmbeddingPostprocessor",      "vis": "EmbeddingVisualizer"},
    "hand_landmark":          {"pre": "LetterboxPreprocessor",         "post": "HandLandmarkPostprocessor",          "vis": "HandLandmarkVisualizer"},
}
