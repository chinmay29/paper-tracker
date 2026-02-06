/**
 * Loading spinner component
 */
function LoadingSpinner({ text = 'Loading...' }) {
    return (
        <div className="loading-spinner" style={{ flexDirection: 'column' }}>
            <div className="spinner" />
            {text && <p className="loading-text">{text}</p>}
        </div>
    );
}

export default LoadingSpinner;
