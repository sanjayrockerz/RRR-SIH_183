"""Controlled V1.1 search; fixed V1 address/time split, validation-only selection."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import joblib, matplotlib.pyplot as plt, numpy as np, pandas as pd, pyarrow.parquet as pq
from sklearn.metrics import precision_recall_curve
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from xgboost import XGBClassifier

ROOT=Path(__file__).resolve().parents[1]; ART=ROOT/"artifacts"; MODELS=ROOT/"models"; TABLE=ROOT/"data/Datasets/processed/rrr_wallet_features_v1_1.parquet"; ART.mkdir(exist_ok=True); MODELS.mkdir(exist_ok=True)
FEATURES=[c for c in pq.ParquetFile(TABLE).schema.names if c not in {"observation_id","address","time_step","label","feature_schema_version"}]

def parts():
    data=pd.read_parquet(TABLE)
    manifest=json.loads((ART/"split_manifests.json").read_text(encoding="utf-8"))
    ids={name:set(manifest["splits"][name]["observation_ids"]) for name in ["train","validation","test"]}
    assert set(data.observation_id)==set().union(*ids.values())
    assert not (ids["train"]&ids["validation"] or ids["train"]&ids["test"] or ids["validation"]&ids["test"])
    return {name:data[data.observation_id.isin(value)].copy() for name,value in ids.items()}

def evaluate(y, p, threshold):
    from training_common import metrics
    return metrics(y.to_numpy(), (p>=threshold).astype(int), p)

def curve(y,p):
    rows=[]
    for t in np.round(np.arange(.05,.801,.01),2):
        r=evaluate(y,p,float(t)); rows.append({"threshold":float(t),"precision":r["precision"],"recall":r["recall"],"f1":r["f1"],"false_positives":r["confusion_matrix"][0][1],"false_negatives":r["confusion_matrix"][1][0]})
    return pd.DataFrame(rows)

def select_points(c):
    recall=c[c.recall>=.80]; high_recall=(recall.sort_values(["precision","threshold"],ascending=[False,True]).iloc[0] if len(recall) else c.sort_values(["recall","precision"],ascending=[False,False]).iloc[0])
    balanced=c[c.recall>=.60]; balanced=(balanced.sort_values(["f1","precision","recall"],ascending=False).iloc[0] if len(balanced) else c.sort_values(["f1","recall"],ascending=False).iloc[0])
    high_precision=c.sort_values(["f1","precision","recall"],ascending=False).iloc[0]
    return {"HIGH_RECALL":high_recall.to_dict(),"BALANCED":balanced.to_dict(),"HIGH_PRECISION":high_precision.to_dict()}

def fit(params, train, val, weight):
    model=XGBClassifier(n_estimators=600,max_depth=params["max_depth"],min_child_weight=params["min_child_weight"],learning_rate=params["learning_rate"],subsample=params["subsample"],colsample_bytree=params["colsample_bytree"],gamma=params["gamma"],max_delta_step=params["max_delta_step"],objective="binary:logistic",eval_metric="aucpr",n_jobs=-1,random_state=42,scale_pos_weight=weight,early_stopping_rounds=35)
    counts=train.address.value_counts(); row_weights=train.address.map(1/counts).to_numpy(dtype=float); class_weights=np.where(train.label.to_numpy()==1,weight,1.0); sample=row_weights*class_weights
    model.fit(train[FEATURES],train.label,sample_weight=sample,eval_set=[(val[FEATURES],val.label)],verbose=False)
    return model

def main():
    p=parts(); train,val,test=p["train"],p["validation"],p["test"]; natural=int((train.label==0).sum())/max(int((train.label==1).sum()),1)
    factors=[.5,1.,1.5,2.,3.]; weight_results=[]
    fixed={"max_depth":6,"min_child_weight":5,"learning_rate":.05,"subsample":.85,"colsample_bytree":.85,"gamma":0,"max_delta_step":1}
    for factor in factors:
        weight=natural*factor; m=fit(fixed,train,val,weight); prob=m.predict_proba(val[FEATURES])[:,1]; best=curve(val.label,prob).sort_values(["f1","recall","precision"],ascending=False).iloc[0]; weight_results.append({"factor":factor,"scale_pos_weight":weight,"validation_pr_auc":float(__import__('sklearn.metrics',fromlist=['average_precision_score']).average_precision_score(val.label,prob)),"validation_recall_at_best_f1":float(best.recall),"validation_f1_at_best_f1":float(best.f1)})
    weight_table=pd.DataFrame(weight_results); selected_weight=float(weight_table.sort_values(["validation_pr_auc","validation_recall_at_best_f1","validation_f1_at_best_f1"],ascending=False).iloc[0].scale_pos_weight)
    configs=[]
    for depth,min_child,lr in [(4,1,.03),(4,5,.05),(6,1,.05),(6,5,.05),(6,10,.08),(8,1,.03),(8,5,.05),(8,10,.08),(4,10,.08),(6,5,.03),(6,5,.08),(8,5,.03)]: configs.append({"max_depth":depth,"min_child_weight":min_child,"learning_rate":lr,"subsample":.85,"colsample_bytree":.85,"gamma":0.5 if depth>=8 else 0,"max_delta_step":1})
    search=[]; best_model=None; best_key=None
    for i,params in enumerate(configs,1):
        m=fit(params,train,val,selected_weight); prob=m.predict_proba(val[FEATURES])[:,1]; c=curve(val.label,prob); row=c.sort_values(["f1","recall"],ascending=False).iloc[0]; from sklearn.metrics import average_precision_score
        result={"trial":i,"params":params,"best_iteration":int(getattr(m,"best_iteration",599)),"validation_pr_auc":float(average_precision_score(val.label,prob)),"validation_recall_at_best_f1":float(row.recall),"validation_f1_at_best_f1":float(row.f1)}; search.append(result); key=(result["validation_pr_auc"],result["validation_recall_at_best_f1"],result["validation_f1_at_best_f1"])
        if best_key is None or key>best_key: best_key=key; best_model=m; best_params=params; best_val_prob=prob
        print(f"trial {i}/{len(configs)} pr_auc={result['validation_pr_auc']:.4f} recall={result['validation_recall_at_best_f1']:.4f} f1={result['validation_f1_at_best_f1']:.4f}")
    pd.DataFrame(weight_results).to_csv(ART/"v1_1_class_weight_search.csv",index=False); pd.DataFrame(search).to_json(ART/"v1_1_hyperparameter_search.json",orient="records",indent=2)
    threshold_df=curve(val.label,best_val_prob); threshold_df.to_csv(ART/"threshold_analysis.csv",index=False); points=select_points(threshold_df)
    prec,rec,_=precision_recall_curve(val.label,best_val_prob); plt.figure(figsize=(7,5)); plt.plot(rec,prec); plt.xlabel("Illicit recall"); plt.ylabel("Illicit precision"); plt.title("V1.1 validation precision-recall curve"); plt.grid(alpha=.2); plt.tight_layout(); plt.savefig(ART/"precision_recall_curve.png",dpi=160); plt.close()
    operating=points["BALANCED"] if points["BALANCED"]["recall"]>=.60 else points["HIGH_RECALL"]; threshold=float(operating["threshold"]); final=evaluate(test.label,best_model.predict_proba(test[FEATURES])[:,1],threshold)
    # Hard negatives and temporal consistency are descriptive only; no test-driven changes.
    test_prob=best_model.predict_proba(test[FEATURES])[:,1]; val_pred=(best_val_prob>=threshold).astype(int); val_copy=val.copy(); val_copy["probability"]=best_val_prob; val_copy["predicted"]=val_pred
    fn=val_copy[(val_copy.label==1)&(val_copy.predicted==0)]; tp=val_copy[(val_copy.label==1)&(val_copy.predicted==1)]; tn=val_copy[(val_copy.label==0)&(val_copy.predicted==0)]
    def dist(frame): return {c:{"mean":float(frame[c].mean()) if len(frame) else None,"median":float(frame[c].median()) if len(frame) else None} for c in FEATURES}
    fn_summary={"false_negative_count":len(fn),"true_positive_count":len(tp),"true_negative_count":len(tn),"false_negative_feature_distribution":dist(fn),"true_positive_feature_distribution":dist(tp),"true_negative_feature_distribution":dist(tn),"systematic_checks":{"low_degree_false_negatives":int((fn.total_degree<=2).sum()),"low_volume_false_negatives":int((fn.total_in+fn.total_out<=1).sum()),"long_lived_false_negatives":int((fn.observation_lifetime>=fn.observation_lifetime.median()).sum()) if len(fn) else 0,"balanced_flow_false_negatives":int(((fn.sent_received_ratio.between(.5,2))).sum())}}
    (ART/"false_negative_analysis.json").write_text(json.dumps(fn_summary,indent=2),encoding="utf-8")
    illicit_wallets=val[val.label==1].groupby("address").size(); early=val[val.time_step<=val.time_step.median()]; late=val[val.time_step>val.time_step.median()]; temporal={"illicit_wallets":int(val.loc[val.label==1,"address"].nunique()),"observations_per_illicit_wallet":{"min":int(illicit_wallets.min()),"median":float(illicit_wallets.median()),"max":int(illicit_wallets.max())},"early_validation":{"time_steps":[int(early.time_step.min()),int(early.time_step.max())],"metrics":evaluate(early.label,best_val_prob[val.time_step<=val.time_step.median()],threshold)},"late_validation":{"time_steps":[int(late.time_step.min()),int(late.time_step.max())],"metrics":evaluate(late.label,best_val_prob[val.time_step>val.time_step.median()],threshold)},"label_noise_note":"Labels are wallet-level; earlier observations may precede the behavior represented by the eventual wallet label. No relabeling was performed."}
    (ART/"temporal_label_consistency.json").write_text(json.dumps(temporal,indent=2),encoding="utf-8")
    # Calibration is assessed on a validation-only inner/holdout partition and not used if PR-AUC degrades.
    split=int(len(val)*.5); cal=CalibratedClassifierCV(FrozenEstimator(best_model),method="sigmoid"); cal.fit(val.iloc[:split][FEATURES],val.iloc[:split].label); cal_prob=cal.predict_proba(val.iloc[split:][FEATURES])[:,1]; raw_prob=best_model.predict_proba(val.iloc[split:][FEATURES])[:,1]
    from sklearn.metrics import average_precision_score
    calibration={"method":"sigmoid","holdout":"validation second half","raw_pr_auc":float(average_precision_score(val.iloc[split:].label,raw_prob)),"calibrated_pr_auc":float(average_precision_score(val.iloc[split:].label,cal_prob)),"used_for_final":False}
    (ART/"calibration_analysis.json").write_text(json.dumps(calibration,indent=2),encoding="utf-8")
    importance={name:float(value) for name,value in sorted(zip(FEATURES,best_model.feature_importances_),key=lambda x:x[1],reverse=True)}
    metadata={"model_name":"RRR wallet behaviour XGBoost","model_version":"rrr_wallet_xgb_v1_1","feature_schema_version":"RRRFeatureSchemaV1.1","feature_order":FEATURES,"decision_threshold":threshold,"operating_point":"BALANCED" if operating is points["BALANCED"] else "HIGH_RECALL","training_rows":len(train),"validation_rows":len(val),"test_rows":len(test),"train_time_range":[1,34],"validation_time_range":[35,41],"test_time_range":[42,49],"scale_pos_weight":selected_weight,"natural_scale_pos_weight":natural,"sample_weight":"1 / training observation count per address, multiplied by class weight","best_hyperparameters":best_params,"metrics":final,"validation_operating_points":points,"feature_importance":importance,"training_timestamp":datetime.now(timezone.utc).isoformat(),"providers_called":[]}
    joblib.dump({"model":best_model,"feature_order":FEATURES,"threshold":threshold,"schema_version":"RRRFeatureSchemaV1.1"},MODELS/"rrr_wallet_xgb_v1_1.joblib"); (MODELS/"rrr_wallet_xgb_v1_1_metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8"); (ART/"v1_1_metrics.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    from sklearn.metrics import average_precision_score
    v1=json.loads((ART/"xgb_metrics.json").read_text(encoding="utf-8")); comparison={"v1":{"accuracy":v1["metrics"]["accuracy"],"macro_f1":v1["metrics"]["macro_f1"],"illicit_f1":v1["metrics"]["class_metrics"]["ILLICIT"]["f1"],"illicit_recall":v1["metrics"]["class_metrics"]["ILLICIT"]["recall"],"pr_auc":v1["metrics"]["pr_auc"],"roc_auc":v1["metrics"]["roc_auc"]},"v1_1":{**{k:final[k] for k in ["accuracy","macro_f1","pr_auc","roc_auc"]},"illicit_f1":final["class_metrics"]["ILLICIT"]["f1"],"illicit_recall":final["class_metrics"]["ILLICIT"]["recall"]},"selection_note":"V1.1 prioritizes illicit recall/F1/PR-AUC; final threshold is validation-selected."}; (ART/"v1_vs_v1_1_comparison.json").write_text(json.dumps(comparison,indent=2),encoding="utf-8")
    print(json.dumps({"features":len(FEATURES),"selected_weight":selected_weight,"operating_points":points,"final_metrics":final,"top10":list(importance)[:10]},indent=2))
if __name__=="__main__": main()
