'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react';

interface WorkflowDetail {
  id: string;
  name: string;
  description?: string;
  entity_type: string;
  is_active: boolean;
  trigger_type: string;
  trigger_config: Record<string, unknown>;
  actions: WorkflowAction[];
  conditions: WorkflowCondition[];
  created_at: string;
}

interface WorkflowAction {
  id: string;
  action_type: string;
  action_config: Record<string, unknown>;
  order: number;
  is_active: boolean;
}

interface WorkflowCondition {
  id: string;
  field_name: string;
  operator: string;
  value?: string;
  logic_operator: string;
}

const ACTION_TYPES = [
  { value: 'send_notification', label: 'Send Notification' },
  { value: 'assign_lead', label: 'Assign Lead' },
  { value: 'create_task', label: 'Create Task' },
  { value: 'update_field', label: 'Update Field' },
  { value: 'send_email', label: 'Send Email' },
];

const OPERATORS = [
  { value: 'equals', label: 'Equals' },
  { value: 'contains', label: 'Contains' },
  { value: 'greater_than', label: 'Greater Than' },
  { value: 'less_than', label: 'Less Than' },
  { value: 'is_empty', label: 'Is Empty' },
  { value: 'is_not_empty', label: 'Is Not Empty' },
];

export default function WorkflowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;

  const [workflow, setWorkflow] = useState<WorkflowDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedSections, setExpandedSections] = useState({
    conditions: true,
    actions: true,
  });
  const [showAddAction, setShowAddAction] = useState(false);
  const [showAddCondition, setShowAddCondition] = useState(false);
  const [newAction, setNewAction] = useState({
    action_type: 'send_notification',
    action_config: {},
  });
  const [newCondition, setNewCondition] = useState({
    field_name: '',
    operator: 'equals',
    value: '',
    logic_operator: 'AND',
  });

  const fetchWorkflow = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/broker/workflows/${workflowId}`);
      if (!response.ok) throw new Error('Failed to fetch workflow');
      const data = await response.json();
      setWorkflow(data);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflow');
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void fetchWorkflow(), 0);
    return () => window.clearTimeout(timer);
  }, [fetchWorkflow]);

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const handleAddAction = async () => {
    try {
      const response = await fetch(`/api/v1/broker/workflows/${workflowId}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newAction,
          order: (workflow?.actions.length || 0) + 1,
        }),
      });
      if (!response.ok) throw new Error('Failed to add action');
      setNewAction({ action_type: 'send_notification', action_config: {} });
      setShowAddAction(false);
      await fetchWorkflow();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add action');
    }
  };

  const handleAddCondition = async () => {
    try {
      const response = await fetch(`/api/v1/broker/workflows/${workflowId}/conditions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCondition),
      });
      if (!response.ok) throw new Error('Failed to add condition');
      setNewCondition({
        field_name: '',
        operator: 'equals',
        value: '',
        logic_operator: 'AND',
      });
      setShowAddCondition(false);
      await fetchWorkflow();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add condition');
    }
  };

  const handleDeleteAction = async (actionId: string) => {
    if (!confirm('Delete this action?')) return;
    try {
      const response = await fetch(
        `/api/v1/broker/workflows/${workflowId}/actions/${actionId}`,
        { method: 'DELETE' }
      );
      if (!response.ok) throw new Error('Failed to delete action');
      await fetchWorkflow();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete action');
    }
  };

  const handleDeleteCondition = async (conditionId: string) => {
    if (!confirm('Delete this condition?')) return;
    try {
      const response = await fetch(
        `/api/v1/broker/workflows/${workflowId}/conditions/${conditionId}`,
        { method: 'DELETE' }
      );
      if (!response.ok) throw new Error('Failed to delete condition');
      await fetchWorkflow();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete condition');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D121F] text-white p-6 flex items-center justify-center">
        <div className="animate-spin inline-block w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="min-h-screen bg-[#0D121F] text-white p-6">
        <div className="max-w-4xl mx-auto bg-red-500/10 border border-red-500 text-red-400 p-4 rounded-lg">
          {error || 'Workflow not found'}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0D121F] text-white p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <button
            onClick={() => router.back()}
            className="text-gray-400 hover:text-white transition mb-4"
          >
            ← Back
          </button>
          <h1 className="text-3xl font-bold">{workflow.name}</h1>
          <div className="w-24"></div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-400 p-4 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Workflow Info */}
        <div className="bg-[#1a2332] border border-gray-700 rounded-lg p-6 mb-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-gray-400 text-sm">Entity Type</p>
              <p className="font-semibold">{workflow.entity_type}</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Trigger Type</p>
              <p className="font-semibold">{workflow.trigger_type}</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Status</p>
              <p className="font-semibold">
                {workflow.is_active ? (
                  <span className="text-green-400">Active</span>
                ) : (
                  <span className="text-yellow-400">Inactive</span>
                )}
              </p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Actions</p>
              <p className="font-semibold">{workflow.actions.length}</p>
            </div>
          </div>
          {workflow.description && (
            <p className="text-gray-400 mt-4 border-t border-gray-700 pt-4">
              {workflow.description}
            </p>
          )}
        </div>

        {/* Conditions Section */}
        <div className="bg-[#1a2332] border border-gray-700 rounded-lg overflow-hidden mb-8">
          <button
            onClick={() => toggleSection('conditions')}
            className="w-full flex items-center justify-between p-6 hover:bg-[#252d3f] transition"
          >
            <h2 className="text-xl font-bold">Conditions</h2>
            {expandedSections.conditions ? (
              <ChevronUp size={20} />
            ) : (
              <ChevronDown size={20} />
            )}
          </button>

          {expandedSections.conditions && (
            <div className="px-6 pb-6 border-t border-gray-700">
              {workflow.conditions.length > 0 ? (
                <div className="space-y-3 mb-4">
                  {workflow.conditions.map((condition) => (
                    <div
                      key={condition.id}
                      className="flex items-center justify-between bg-[#0D121F] p-4 rounded-lg"
                    >
                      <div className="flex-1">
                        <p className="text-gray-400 text-sm">
                          {condition.field_name}{' '}
                          <span className="text-cyan-400">
                            {OPERATORS.find((o) => o.value === condition.operator)?.label}
                          </span>{' '}
                          {condition.value}
                        </p>
                        {condition.logic_operator && (
                          <p className="text-xs text-gray-500 mt-1">
                            {condition.logic_operator}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={() => handleDeleteCondition(condition.id)}
                        className="text-red-500 hover:text-red-400 transition"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400 text-sm mb-4">No conditions set yet</p>
              )}

              {showAddCondition ? (
                <div className="bg-[#0D121F] p-4 rounded-lg space-y-3">
                  <input
                    type="text"
                    placeholder="Field name"
                    value={newCondition.field_name}
                    onChange={(e) =>
                      setNewCondition({
                        ...newCondition,
                        field_name: e.target.value,
                      })
                    }
                    className="w-full bg-[#1a2332] border border-gray-600 rounded px-3 py-2 text-white text-sm placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                  />
                  <select
                    value={newCondition.operator}
                    onChange={(e) =>
                      setNewCondition({
                        ...newCondition,
                        operator: e.target.value,
                      })
                    }
                    className="w-full bg-[#1a2332] border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-cyan-500 focus:outline-none"
                  >
                    {OPERATORS.map((op) => (
                      <option key={op.value} value={op.value}>
                        {op.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    placeholder="Value (optional)"
                    value={newCondition.value}
                    onChange={(e) =>
                      setNewCondition({
                        ...newCondition,
                        value: e.target.value,
                      })
                    }
                    className="w-full bg-[#1a2332] border border-gray-600 rounded px-3 py-2 text-white text-sm placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleAddCondition}
                      className="flex-1 bg-cyan-500 hover:bg-cyan-600 text-black font-semibold py-2 rounded text-sm transition"
                    >
                      Add Condition
                    </button>
                    <button
                      onClick={() => setShowAddCondition(false)}
                      className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-semibold py-2 rounded text-sm transition"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddCondition(true)}
                  className="w-full bg-[#0D121F] border border-dashed border-gray-600 rounded-lg p-3 text-gray-400 hover:text-gray-300 hover:border-gray-500 transition flex items-center justify-center gap-2"
                >
                  <Plus size={18} />
                  Add Condition
                </button>
              )}
            </div>
          )}
        </div>

        {/* Actions Section */}
        <div className="bg-[#1a2332] border border-gray-700 rounded-lg overflow-hidden">
          <button
            onClick={() => toggleSection('actions')}
            className="w-full flex items-center justify-between p-6 hover:bg-[#252d3f] transition"
          >
            <h2 className="text-xl font-bold">Actions</h2>
            {expandedSections.actions ? (
              <ChevronUp size={20} />
            ) : (
              <ChevronDown size={20} />
            )}
          </button>

          {expandedSections.actions && (
            <div className="px-6 pb-6 border-t border-gray-700">
              {workflow.actions.length > 0 ? (
                <div className="space-y-3 mb-4">
                  {workflow.actions.map((action) => (
                    <div
                      key={action.id}
                      className="flex items-center justify-between bg-[#0D121F] p-4 rounded-lg"
                    >
                      <div className="flex-1">
                        <p className="text-gray-400 text-sm">
                          <span className="text-cyan-400 font-semibold">
                            {ACTION_TYPES.find((a) => a.value === action.action_type)
                              ?.label}
                          </span>
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Order: {action.order} · Status:{' '}
                          {action.is_active ? 'Active' : 'Inactive'}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDeleteAction(action.id)}
                        className="text-red-500 hover:text-red-400 transition"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400 text-sm mb-4">No actions set yet</p>
              )}

              {showAddAction ? (
                <div className="bg-[#0D121F] p-4 rounded-lg space-y-3">
                  <select
                    value={newAction.action_type}
                    onChange={(e) =>
                      setNewAction({
                        ...newAction,
                        action_type: e.target.value,
                      })
                    }
                    className="w-full bg-[#1a2332] border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-cyan-500 focus:outline-none"
                  >
                    {ACTION_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                  <div className="flex gap-2">
                    <button
                      onClick={handleAddAction}
                      className="flex-1 bg-cyan-500 hover:bg-cyan-600 text-black font-semibold py-2 rounded text-sm transition"
                    >
                      Add Action
                    </button>
                    <button
                      onClick={() => setShowAddAction(false)}
                      className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-semibold py-2 rounded text-sm transition"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddAction(true)}
                  className="w-full bg-[#0D121F] border border-dashed border-gray-600 rounded-lg p-3 text-gray-400 hover:text-gray-300 hover:border-gray-500 transition flex items-center justify-center gap-2"
                >
                  <Plus size={18} />
                  Add Action
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
