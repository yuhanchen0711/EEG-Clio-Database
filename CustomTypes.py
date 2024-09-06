class CustomType:
    def __init__(self, verify, inputstructure):
        self.check = verify
        self.inputs = inputstructure
        self.structureValue = None

    def verify(self, property, input):
        return self.check(property, input)

    def inputstructure(self, id):
        if not self.structureValue:
            self.structure, self.structureValue = self.inputs(id)
            return self.structure
        return self.inputs(id)[0]
    def getStructureValue(self):
        return self.structureValue
    
