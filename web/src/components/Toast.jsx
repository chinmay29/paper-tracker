import { useState, useEffect, useCallback } from 'react';

/**
 * Toast notification component for showing progress and status messages
 */
function Toast({ message, type = 'info', progress = null, onDismiss }) {
    const bgColors = {
        info: 'linear-gradient(135deg, #3b82f6, #2563eb)',
        success: 'linear-gradient(135deg, #22c55e, #16a34a)',
        warning: 'linear-gradient(135deg, #f59e0b, #d97706)',
        error: 'linear-gradient(135deg, #ef4444, #dc2626)',
    };

    return (
        <div style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            background: bgColors[type] || bgColors.info,
            color: '#fff',
            padding: '16px 20px',
            borderRadius: '12px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            minWidth: '280px',
            maxWidth: '400px',
            zIndex: 1000,
            animation: 'slideIn 0.3s ease-out',
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                    <p style={{ margin: 0, fontWeight: '500', fontSize: '14px' }}>{message}</p>
                    {progress !== null && (
                        <div style={{ marginTop: '10px' }}>
                            <div style={{
                                background: 'rgba(255,255,255,0.3)',
                                borderRadius: '4px',
                                height: '6px',
                                overflow: 'hidden',
                            }}>
                                <div style={{
                                    background: '#fff',
                                    height: '100%',
                                    width: `${Math.min(100, progress)}%`,
                                    transition: 'width 0.3s ease',
                                    borderRadius: '4px',
                                }} />
                            </div>
                            <p style={{ margin: '6px 0 0', fontSize: '12px', opacity: 0.9 }}>
                                {progress.toFixed(0)}% complete
                            </p>
                        </div>
                    )}
                </div>
                {onDismiss && (
                    <button
                        onClick={onDismiss}
                        style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#fff',
                            cursor: 'pointer',
                            fontSize: '16px',
                            padding: '0 0 0 12px',
                            opacity: 0.7,
                        }}
                    >
                        ✕
                    </button>
                )}
            </div>
        </div>
    );
}

/**
 * Hook to manage toast notifications
 */
export function useToast() {
    const [toast, setToast] = useState(null);

    const showToast = useCallback((message, type = 'info', progress = null, duration = null) => {
        setToast({ message, type, progress });

        if (duration) {
            setTimeout(() => setToast(null), duration);
        }
    }, []);

    const updateProgress = useCallback((progress, message = null) => {
        setToast(prev => prev ? { ...prev, progress, ...(message ? { message } : {}) } : null);
    }, []);

    const hideToast = useCallback(() => setToast(null), []);

    const ToastComponent = toast ? (
        <Toast
            message={toast.message}
            type={toast.type}
            progress={toast.progress}
            onDismiss={hideToast}
        />
    ) : null;

    return { showToast, updateProgress, hideToast, ToastComponent };
}

export default Toast;
