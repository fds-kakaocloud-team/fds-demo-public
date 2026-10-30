"""Train a separate synthetic time/location demonstration model."""
import csv,json
from pathlib import Path
import joblib,numpy as np,sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score,confusion_matrix,classification_report
from sklearn.model_selection import train_test_split
with open('data/transactions.csv', encoding='utf-8', newline='') as f: rows=list(csv.DictReader(f))
features=['hour','distance_from_last_km']
X=np.array([[float(r[k]) for k in features] for r in rows]); y=np.array([int(r['is_fraud']) for r in rows])
a,test,b,yt=train_test_split(X,y,test_size=.2,random_state=42,stratify=y)
train,val,yt_train,yv=train_test_split(a,b,test_size=.25,random_state=42,stratify=b)
m=RandomForestClassifier(n_estimators=200,min_samples_leaf=100,class_weight='balanced',random_state=42,n_jobs=-1).fit(train,yt_train)
s=m.predict_proba(val)[:,1]
_,threshold=max((balanced_accuracy_score(yv,s>=t),float(t)) for t in np.arange(.1,.91,.01))
m.fit(a,b); scores=m.predict_proba(test)[:,1]; predictions=scores>=threshold
report={'features':features,'threshold':threshold,'split':'60/20/20 stratified; seed 42','confusion_matrix':confusion_matrix(yt,predictions).tolist(),'classification_report':classification_report(yt,predictions,output_dict=True,zero_division=0)}
joblib.dump({'model':m,'features':features,'decision_threshold':threshold,'sklearn_version':sklearn.__version__},'models/context_model.pkl')
Path('models/context_evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
