
import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Plus, Trash2 } from 'lucide-react';

interface KeyValuePair {
  key: string;
  value: string;
}

interface KeyValueInputProps {
  label: string;
  placeholder?: string;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
  pairs: KeyValuePair[];
  onChange: (pairs: KeyValuePair[]) => void;
  className?: string;
}

export function KeyValueInput({
  label,
  placeholder = "Add key-value pairs",
  keyPlaceholder = "Key",
  valuePlaceholder = "Value",
  pairs,
  onChange,
  className = ""
}: KeyValueInputProps) {
  const addPair = () => {
    onChange([...pairs, { key: '', value: '' }]);
  };

  const removePair = (index: number) => {
    onChange(pairs.filter((_, i) => i !== index));
  };

  const updatePair = (index: number, field: 'key' | 'value', value: string) => {
    const updatedPairs = pairs.map((pair, i) => 
      i === index ? { ...pair, [field]: value } : pair
    );
    onChange(updatedPairs);
  };

  return (
    <div className={`space-y-3 ${className}`}>
      <Label className="text-sm font-medium text-foreground">{label}</Label>
      
      {pairs.length === 0 ? (
        <div className="text-center py-8 border-2 border-dashed border-muted-foreground/25 rounded-lg bg-muted/5">
          <div className="flex flex-col items-center gap-3">
            {/* <div className="h-12 w-12 rounded-full bg-muted/20 flex items-center justify-center">
              <Plus className="h-6 w-6 text-muted-foreground" />
            </div> */}
            <div>
              <p className="text-sm font-medium text-foreground mb-1">No {label.toLowerCase().includes('headers') ? 'Header' : 'Environment Variable'} added yet</p>
              {/* <p className="text-xs text-muted-foreground">{placeholder}</p> */}
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addPair}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Add {label.toLowerCase().includes('headers') ? 'Header' : 'Environment Variable'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {pairs.map((pair, index) => (
            <div key={index} className="flex items-center gap-2">
              <div className="flex-1">
                <Input
                  placeholder={keyPlaceholder}
                  value={pair.key}
                  onChange={(e) => updatePair(index, 'key', e.target.value)}
                  className="font-mono text-sm"
                />
              </div>
              <div className="flex-1">
                <Input
                  placeholder={valuePlaceholder}
                  value={pair.value}
                  onChange={(e) => updatePair(index, 'value', e.target.value)}
                  className="font-mono text-sm"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => removePair(index)}
                className="h-9 w-9 p-0 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addPair}
            className="w-full flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Add {label.toLowerCase()}
          </Button>
        </div>
      )}
    </div>
  );
}
