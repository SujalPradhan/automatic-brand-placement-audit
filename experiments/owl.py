"""OWLv2 helpers: per-box embeddings, text queries and one-shot brand queries."""
import torch
import torch.nn.functional as F
from torchvision.ops import nms
from transformers import Owlv2ForObjectDetection, Owlv2Processor

from common import iou

MODEL_ID = "google/owlv2-base-patch16-ensemble"
DEV = "mps" if torch.backends.mps.is_available() else "cpu"
proc = Owlv2Processor.from_pretrained(MODEL_ID)
model = Owlv2ForObjectDetection.from_pretrained(MODEL_ID).to(DEV).eval()


@torch.no_grad()
def embed(im_rgb):
    """All OWLv2 box proposals for an RGB frame: boxes (N,4 xyxy px), image feats (N,D), class embeds (N,E)."""
    pv = proc(images=im_rgb, return_tensors="pt")["pixel_values"].to(DEV)
    fmap, _ = model.image_embedder(pixel_values=pv)
    b, ph, pw, d = fmap.shape
    feats = fmap.reshape(b, ph * pw, d)
    cx, cy, bw, bh = model.box_predictor(feats, fmap)[0].unbind(-1)
    side = max(im_rgb.shape[:2])  # processor pads to a square
    boxes = torch.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], -1) * side
    _, cemb = model.class_predictor(feats)
    return boxes, feats[0], F.normalize(cemb[0], dim=-1)


@torch.no_grad()
def text_scores(feats, prompts):
    t = proc(text=prompts, return_tensors="pt").to(DEV)
    q = model.owlv2.get_text_features(input_ids=t["input_ids"], attention_mask=t["attention_mask"])
    q = q.pooler_output if hasattr(q, "pooler_output") else q
    logits, _ = model.class_predictor(feats[None], q[None])
    return torch.sigmoid(logits[0])


def ref_embedding(im_rgb, box):
    """Class embedding of the proposal that best overlaps a hand-picked reference box."""
    boxes, _, cemb = embed(im_rgb)
    ious = torch.tensor([iou(b, box) for b in boxes.cpu().tolist()])
    return cemb[int(ious.argmax())]


def top_boxes(boxes, scores, thr, nms_iou=0.3):
    keep = scores > thr
    if not keep.any():
        return []
    b, s = boxes[keep].float().cpu(), scores[keep].float().cpu()
    k = nms(b, s, nms_iou)
    return [[*[round(float(v), 1) for v in b[i]], round(float(s[i]), 4)] for i in k]
