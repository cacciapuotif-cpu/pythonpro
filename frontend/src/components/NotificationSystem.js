/**
 * Sistema di notifiche avanzato con animazioni e auto-dismiss
 */

import React, { useEffect, useState } from 'react';
import { useAppContext } from '../context/AppContext';
import './NotificationSystem.css';

const NotificationSystem = () => {
  const { state, removeNotification } = useAppContext();
  const [mounted, setMounted] = useState({});

  useEffect(() => {
    // Auto-hide notifications
    state.ui.notifications.forEach(notification => {
      if (notification.autoHide && notification.duration) {
        const timer = setTimeout(() => {
          removeNotification(notification.id);
        }, notification.duration);

        return () => clearTimeout(timer);
      }
    });
  }, [state.ui.notifications, removeNotification]);

  const handleClose = (id) => {
    setMounted(prev => ({ ...prev, [id]: false }));
    setTimeout(() => {
      removeNotification(id);
    }, 300); // Wait for exit animation
  };

  const getIcon = (type) => {
    switch (type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'info':
      default:
        return 'ℹ️';
    }
  };

  if (state.ui.notifications.length === 0) {
    return null;
  }

  return (
    <div className="notification-container">
      {state.ui.notifications.map((notification) => (
        <div
          key={notification.id}
          className={`notification notification-${notification.type} ${
            mounted[notification.id] === false ? 'notification-exit' : 'notification-enter'
          }`}
          onAnimationEnd={() => {
            if (mounted[notification.id] === false) {
              removeNotification(notification.id);
            }
          }}
        >
          <div className="notification-icon">
            {getIcon(notification.type)}
          </div>

          <div className="notification-content">
            {notification.title && (
              <div className="notification-title">
                {notification.title}
              </div>
            )}
            <div className="notification-message">
              {notification.message}
            </div>
          </div>

          <button
            className="notification-close"
            onClick={() => handleClose(notification.id)}
            aria-label="Chiudi notifica"
          >
            ×
          </button>

          {notification.autoHide && notification.duration && (
            <div
              className="notification-progress"
              style={{
                animationDuration: `${notification.duration}ms`
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
};

export default NotificationSystem;