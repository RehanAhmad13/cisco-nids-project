
from sklearn.preprocessing import LabelEncoder

class LabelEncoderExt:
    def __init__(self):
        self.le = LabelEncoder()
    def fit(self, data):
        self.le = self.le.fit(list(data) + ['Unknown'])
        self.classes_ = self.le.classes_
        return self
    def transform(self, data):
        arr = []
        for x in data:
            arr.append(x if x in self.classes_ else 'Unknown')
        return self.le.transform(arr)